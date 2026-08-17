"""Auth edge cases, direct tests for the notification layer, and worker
registration validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from shared_core.events.base import BaseEvent

from app.events.domain_events import APIVersionReleasedEvent, DeveloperRegisteredEvent
from app.services.notifications import DeveloperNotifier, NotifyingPublisher
from app.workers.registrar import (
    register_api_version_lifecycle_sweep,
    register_credential_expiry_sweep,
    register_quota_reset_sweep,
    register_sandbox_reset_sweep,
    register_statistics_rollup,
)
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/developers/profile", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_no_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/developers/profile")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/developers/profile", headers=headers)
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
        headers = auth_headers(organization_id=uuid4(), roles=["  Api_Platform_Admin  "])
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestDeveloperNotifier:
    async def test_notify_developer_approved(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_developer_approved(email="a@example.com")
        assert manager.calls[0]["topic"] == "public_api_platform.developer_approved"

    async def test_notify_application_approved(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_application_approved(application_name="App")
        assert manager.calls[0]["topic"] == "public_api_platform.application_approved"

    async def test_notify_api_version_released(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_api_version_released(product_name="P", version="1.0.0")
        assert manager.calls[0]["topic"] == "public_api_platform.api_version_released"

    async def test_notify_quota_warning(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_quota_warning(quota_type="api_calls", used_percent=95.0)
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_deprecation_notice(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_deprecation_notice(product_name="P", version="1.0.0")
        assert manager.calls[0]["topic"] == "public_api_platform.deprecation_notice"

    async def test_notify_credential_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_credential_expiring(
            credential_kind="API key", expires_at="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "public_api_platform.credential_expiring"

    async def test_notify_webhook_failure(self) -> None:
        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_webhook_failure(
            webhook_url="https://x.example/hook", reason="timeout"
        )
        assert manager.calls[0]["topic"] == "public_api_platform.webhook_failure"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DeveloperRegisteredEvent(
            source_service="public-api-platform",
            payload={"developer_account_id": "d-1", "email": "a@example.com"},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []  # not a mapped event -- no notification fired

    async def test_api_version_released_fans_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = DeveloperNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = APIVersionReleasedEvent(
            source_service="public-api-platform",
            payload={
                "api_version_id": "v-1",
                "api_product_id": "p-1",
                "product_name": "Weather API",
                "version": "2.0.0",
            },
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "public_api_platform.api_version_released"


class TestRegistrar:
    def test_rejects_non_positive_interval(self) -> None:
        manager = MagicMock()
        with pytest.raises(ValueError, match="must be positive"):
            register_credential_expiry_sweep(manager, lambda job: None, interval_seconds=0)

    def test_registers_credential_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_credential_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_quota_reset_sweep(self) -> None:
        manager = MagicMock()
        register_quota_reset_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_api_version_lifecycle_sweep(self) -> None:
        manager = MagicMock()
        register_api_version_lifecycle_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_statistics_rollup(self) -> None:
        manager = MagicMock()
        register_statistics_rollup(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_sandbox_reset_sweep(self) -> None:
        manager = MagicMock()
        register_sandbox_reset_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called
