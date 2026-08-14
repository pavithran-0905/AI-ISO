"""Auth edge cases, direct tests for the notification layer, and worker
registration validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from shared_core.events.base import BaseEvent

from app.events.domain_events import (
    MobileDeviceRegisteredEvent,
    MobileLoginSucceededEvent,
    SynchronizationFailedEvent,
)
from app.services.notifications import MobileNotifier, NotifyingPublisher
from app.workers.registrar import (
    register_app_version_compliance_sweep,
    register_push_delivery_retry_sweep,
    register_session_expiry_sweep,
    register_sync_queue_retry_sweep,
    register_token_expiry_sweep,
)
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/mobile/profile", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_no_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/mobile/profile")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/mobile/profile", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.get("/mobile/statistics", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Mobile_Admin  "])
        response = await client.get("/mobile/statistics", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestMobileNotifier:
    async def test_notify_new_device_login(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_new_device_login(device_identifier="dev-1", platform="android")
        assert manager.calls[0]["topic"] == "mobile_api.new_device_login"

    async def test_notify_device_revoked(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_device_revoked(device_identifier="dev-1")
        assert manager.calls[0]["topic"] == "mobile_api.device_revoked"

    async def test_notify_app_update_available(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_app_update_available(platform="ios", recommended_version="2.0.0")
        assert manager.calls[0]["topic"] == "mobile_api.app_update_available"

    async def test_notify_forced_upgrade(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_forced_upgrade(platform="ios", minimum_version="2.0.0")
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_synchronization_failed(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_synchronization_failed(device_identifier="dev-1", reason="conflict")
        assert manager.calls[0]["topic"] == "mobile_api.synchronization_failed"

    async def test_notify_security_alert(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_security_alert(device_identifier="dev-1", reason="jailbroken")
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_session_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_session_expiring(
            device_identifier="dev-1", expires_at="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "mobile_api.session_expiring"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = MobileDeviceRegisteredEvent(
            source_service="mobile-api-service",
            payload={"device_id": "d-1", "platform": "android", "trust_status": "pending"},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []  # not a mapped event -- no notification fired

    async def test_new_device_login_fans_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = MobileLoginSucceededEvent(
            source_service="mobile-api-service",
            payload={
                "device_id": "d-1",
                "device_identifier": "dev-1",
                "platform": "android",
                "user_id": "u1",
                "auth_method": "jwt",
                "is_new_device": True,
            },
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "mobile_api.new_device_login"

    async def test_returning_device_login_does_not_fan_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = MobileLoginSucceededEvent(
            source_service="mobile-api-service",
            payload={
                "device_id": "d-1",
                "device_identifier": "dev-1",
                "platform": "android",
                "user_id": "u1",
                "auth_method": "jwt",
                "is_new_device": False,
            },
        )
        await publisher(event)
        assert manager.calls == []

    async def test_synchronization_failed_fans_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = MobileNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = SynchronizationFailedEvent(
            source_service="mobile-api-service",
            payload={
                "sync_job_id": "j-1",
                "device_id": "d-1",
                "device_identifier": "dev-1",
                "reason": "conflict",
            },
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "mobile_api.synchronization_failed"


class TestRegistrar:
    def test_rejects_non_positive_interval(self) -> None:
        manager = MagicMock()
        with pytest.raises(ValueError, match="must be positive"):
            register_session_expiry_sweep(manager, lambda job: None, interval_seconds=0)

    def test_registers_session_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_session_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_token_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_token_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_sync_queue_retry_sweep(self) -> None:
        manager = MagicMock()
        register_sync_queue_retry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_push_delivery_retry_sweep(self) -> None:
        manager = MagicMock()
        register_push_delivery_retry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_app_version_compliance_sweep(self) -> None:
        manager = MagicMock()
        register_app_version_compliance_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called
