"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import (
    ConfigurationChangedEvent,
    FeatureFlagUpdatedEvent,
    PlatformHealthChangedEvent,
    TenantCreatedEvent,
)
from app.services.notifications import AdminNotifier, NotifyingPublisher
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/admin/tenants", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/admin/tenants", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post(
            "/admin/tenants",
            json={"organization_ref_id": str(uuid4()), "name": "Tenant A"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Platform_Admin  "])
        response = await client.get("/admin/tenants", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestAdminNotifier:
    async def test_notify_maintenance_scheduled(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_maintenance_scheduled(
            maintenance_window_id="m-1", starts_at="2026-06-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "administration_portal.maintenance_scheduled"

    async def test_notify_tenant_provisioned(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_tenant_provisioned(tenant_id="t-1", name="Tenant A")
        assert manager.calls[0]["topic"] == "administration_portal.tenant_provisioned"

    async def test_notify_platform_issue(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_platform_issue(component="database", status="unhealthy")
        assert manager.calls[0]["priority"].name == "CRITICAL"

    async def test_notify_security_event(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_security_event(
            security_event_id="e-1", kind="login_failure", severity="low"
        )
        assert manager.calls[0]["topic"] == "administration_portal.security_event"

    async def test_notify_license_expiration(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_license_expiration(customer_id="c-1", days_remaining=5)
        assert manager.calls[0]["topic"] == "administration_portal.license_expiration"

    async def test_notify_feature_enabled(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_feature_enabled(feature_flag_id="f-1", name="new-ui")
        assert manager.calls[0]["topic"] == "administration_portal.feature_enabled"

    async def test_notify_configuration_changed(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_configuration_changed(key="feature_x", environment="production")
        assert manager.calls[0]["topic"] == "administration_portal.configuration_changed"

    async def test_notify_health_degradation(self) -> None:
        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_health_degradation(component="cache", status="degraded")
        assert manager.calls[0]["notification_type"] is NotificationType.WARNING


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = TenantCreatedEvent(
            source_service="administration-portal-service",
            payload={"tenant_id": "t-1", "organization_ref_id": "o-1", "name": "Tenant A"},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls[0]["topic"] == "administration_portal.tenant_provisioned"

    async def test_configuration_changed_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = ConfigurationChangedEvent(
            source_service="administration-portal-service",
            payload={"key": "feature_x", "environment": "production"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "administration_portal.configuration_changed"

    async def test_feature_flag_updated_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = FeatureFlagUpdatedEvent(
            source_service="administration-portal-service",
            payload={"feature_flag_id": "f-1", "name": "new-ui"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "administration_portal.feature_enabled"

    async def test_platform_health_changed_unhealthy_triggers_platform_issue(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = PlatformHealthChangedEvent(
            source_service="administration-portal-service",
            payload={"component": "database", "status": "unhealthy"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "administration_portal.platform_issue"

    async def test_platform_health_changed_degraded_triggers_health_degradation(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = PlatformHealthChangedEvent(
            source_service="administration-portal-service",
            payload={"component": "cache", "status": "degraded"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "administration_portal.health_degradation"

    async def test_platform_health_changed_healthy_does_not_notify(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = PlatformHealthChangedEvent(
            source_service="administration-portal-service",
            payload={"component": "cache", "status": "healthy"},
        )
        await publisher(event)
        assert manager.calls == []

    async def test_unmapped_event_does_not_notify(self) -> None:
        from app.events.domain_events import SecurityPolicyUpdatedEvent

        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = AdminNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = SecurityPolicyUpdatedEvent(
            source_service="administration-portal-service", payload={"key": "password_policy"}
        )
        await publisher(event)
        assert manager.calls == []
