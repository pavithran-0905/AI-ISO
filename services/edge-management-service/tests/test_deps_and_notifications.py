"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import DeviceOfflineEvent, EdgeSiteRegisteredEvent, OTACompletedEvent
from app.services.notifications import EdgeNotifier, NotifyingPublisher
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/edge/devices", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/edge/devices", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post("/edge/sites", json={"name": "s1"}, headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Device_Admin  "])
        response = await client.get("/edge/devices", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestEdgeNotifier:
    async def test_notify_device_offline(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_device_offline(device_id="d-1", device_name="plc-1")
        assert manager.calls[0]["topic"] == "edge_management.device_offline"

    async def test_notify_synchronization_failed(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_synchronization_failed(
            device_id="d-1", sync_id="s-1", error_message="dropped"
        )
        assert manager.calls[0]["topic"] == "edge_management.synchronization_failed"

    async def test_notify_ota_failed(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_ota_failed(device_id="d-1", update_id="u-1")
        assert manager.calls[0]["priority"].name == "CRITICAL"

    async def test_notify_firmware_update_available(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_firmware_update_available(
            device_id="d-1", current_version="1.0.0", available_version="1.1.0"
        )
        assert manager.calls[0]["topic"] == "edge_management.firmware_update_available"

    async def test_notify_security_issue(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_security_issue(device_id="d-1", detail="unauthorized login")
        assert manager.calls[0]["topic"] == "edge_management.security_issue"

    async def test_notify_low_storage(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_low_storage(device_id="d-1", free_fraction=0.05)
        assert "5%" in manager.calls[0]["body"]

    async def test_notify_temperature_alert(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_temperature_alert(device_id="d-1", reading_celsius=95.5)
        assert manager.calls[0]["topic"] == "edge_management.temperature_alert"

    async def test_notify_certificate_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_certificate_expiring(
            device_id="d-1", expires_at="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["notification_type"] is NotificationType.WARNING


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = EdgeSiteRegisteredEvent(source_service="edge-management-service", payload={})
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []

    async def test_device_offline_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DeviceOfflineEvent(
            source_service="edge-management-service", payload={"device_id": "d-1"}
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "edge_management.device_offline"

    async def test_ota_completed_failed_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = OTACompletedEvent(
            source_service="edge-management-service",
            payload={"device_id": "d-1", "update_id": "u-1", "status": "failed"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "edge_management.ota_failed"

    async def test_ota_completed_success_does_not_notify(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = OTACompletedEvent(
            source_service="edge-management-service",
            payload={"device_id": "d-1", "update_id": "u-1", "status": "completed"},
        )
        await publisher(event)
        assert manager.calls == []
