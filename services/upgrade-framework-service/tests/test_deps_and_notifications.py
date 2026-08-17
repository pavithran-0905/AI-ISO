"""Auth edge cases, direct tests for the notification layer, and worker
registration validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from shared_core.events.base import BaseEvent

from app.events.domain_events import ReleasePublishedEvent, UpgradeScheduledEvent
from app.services.notifications import NotifyingPublisher, UpgradeNotifier
from app.workers.registrar import (
    register_health_gate_enforcement,
    register_migration_timeout_sweep,
    register_release_adoption_sweep,
    register_statistics_rollup,
    register_upgrade_job_timeout_sweep,
)
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/statistics", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_no_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/statistics")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Upgrade_Admin  "])
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestUpgradeNotifier:
    async def test_notify_upgrade_available(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_upgrade_available(version="1.2.0")
        assert manager.calls[0]["topic"] == "upgrade_framework.upgrade_available"

    async def test_notify_upgrade_scheduled(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_upgrade_scheduled(plan_name="rolling-upgrade")
        assert manager.calls[0]["topic"] == "upgrade_framework.upgrade_scheduled"

    async def test_notify_upgrade_failed(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_upgrade_failed(reason="timeout")
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_rollback_completed(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_rollback_completed(to_version="1.0.0")
        assert manager.calls[0]["topic"] == "upgrade_framework.rollback_completed"

    async def test_notify_compatibility_issue(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_compatibility_issue(
            compatibility_type="api", detail="breaking change"
        )
        assert manager.calls[0]["topic"] == "upgrade_framework.compatibility_issue"

    async def test_notify_migration_failed(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_migration_failed(
            migration_type="database_schema", detail="constraint violation"
        )
        assert manager.calls[0]["topic"] == "upgrade_framework.migration_failed"

    async def test_notify_release_published(self) -> None:
        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_release_published(version_label="1.2.0")
        assert manager.calls[0]["topic"] == "upgrade_framework.release_published"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = UpgradeScheduledEvent(
            source_service="upgrade-framework-service",
            payload={"upgrade_job_id": "j-1", "upgrade_plan_id": "p-1"},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []  # not a mapped event -- no notification fired

    async def test_release_published_fans_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = UpgradeNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = ReleasePublishedEvent(
            source_service="upgrade-framework-service",
            payload={"release_channel_id": "c-1", "version_label": "1.2.0"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "upgrade_framework.release_published"


class TestRegistrar:
    def test_rejects_non_positive_interval(self) -> None:
        manager = MagicMock()
        with pytest.raises(ValueError, match="must be positive"):
            register_upgrade_job_timeout_sweep(manager, lambda job: None, interval_seconds=0)

    def test_registers_upgrade_job_timeout_sweep(self) -> None:
        manager = MagicMock()
        register_upgrade_job_timeout_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_migration_timeout_sweep(self) -> None:
        manager = MagicMock()
        register_migration_timeout_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_release_adoption_sweep(self) -> None:
        manager = MagicMock()
        register_release_adoption_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_health_gate_enforcement(self) -> None:
        manager = MagicMock()
        register_health_gate_enforcement(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_statistics_rollup(self) -> None:
        manager = MagicMock()
        register_statistics_rollup(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called
