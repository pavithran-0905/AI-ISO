"""Auth edge cases, direct tests for the notification layer, and worker
registration validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from shared_core.events.base import BaseEvent

from app.events.domain_events import InstallationStartedEvent, RollbackCompletedEvent
from app.services.notifications import DeploymentNotifier, NotifyingPublisher
from app.workers.registrar import (
    register_certificate_expiry_sweep,
    register_deployment_job_timeout_sweep,
    register_installation_session_expiry_sweep,
    register_statistics_rollup,
    register_upgrade_availability_sweep,
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
        headers = auth_headers(organization_id=uuid4(), roles=["  Installation_Admin  "])
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestDeploymentNotifier:
    async def test_notify_installation_failed(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_installation_failed(reason="disk full")
        assert manager.calls[0]["topic"] == "installation_deployment.installation_failed"

    async def test_notify_deployment_failed(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_deployment_failed(job_type="deploy", reason="timeout")
        assert manager.calls[0]["topic"] == "installation_deployment.deployment_failed"

    async def test_notify_upgrade_available(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_upgrade_available(version="1.2.0")
        assert manager.calls[0]["topic"] == "installation_deployment.upgrade_available"

    async def test_notify_upgrade_failed(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_upgrade_failed(to_version="1.2.0", reason="migration error")
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_rollback_completed(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_rollback_completed(to_version="1.0.0")
        assert manager.calls[0]["topic"] == "installation_deployment.rollback_completed"

    async def test_notify_certificate_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_certificate_expiring(
            common_name="aiios.local", not_after="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "installation_deployment.certificate_expiring"

    async def test_notify_validation_failed(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_validation_failed(check_type="cpu", detail="low cpu")
        assert manager.calls[0]["topic"] == "installation_deployment.validation_failed"

    async def test_notify_infrastructure_issue(self) -> None:
        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_infrastructure_issue(message="disk pressure detected")
        assert manager.calls[0]["topic"] == "installation_deployment.infrastructure_issue"
        assert manager.calls[0]["priority"].name == "HIGH"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = InstallationStartedEvent(
            source_service="installation-deployment-service",
            payload={"installation_session_id": "s-1", "mode": "cli"},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []  # not a mapped event -- no notification fired

    async def test_rollback_completed_fans_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = DeploymentNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = RollbackCompletedEvent(
            source_service="installation-deployment-service",
            payload={"deployment_job_id": "j-1", "status": "succeeded", "to_version": "1.0.0"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "installation_deployment.rollback_completed"


class TestRegistrar:
    def test_rejects_non_positive_interval(self) -> None:
        manager = MagicMock()
        with pytest.raises(ValueError, match="must be positive"):
            register_installation_session_expiry_sweep(
                manager, lambda job: None, interval_seconds=0
            )

    def test_registers_installation_session_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_installation_session_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_deployment_job_timeout_sweep(self) -> None:
        manager = MagicMock()
        register_deployment_job_timeout_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_certificate_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_certificate_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_statistics_rollup(self) -> None:
        manager = MagicMock()
        register_statistics_rollup(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_upgrade_availability_sweep(self) -> None:
        manager = MagicMock()
        register_upgrade_availability_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called
