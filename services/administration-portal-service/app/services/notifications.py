"""Notifications (docs/070 "NOTIFICATIONS", integrating Prompt 025).

**Three of the eight notification kinds have a domain event behind
them** (Tenant Provisioned, Configuration Changed, Feature Enabled) and
are dispatched by :class:`NotifyingPublisher`, an ``EventPublisher``
that wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- exactly
the pattern ``services/license-billing-service/app/services/notifications.py``
established. ``PlatformHealthChanged`` fans out to one of two
notifications depending on its own payload's severity.

**The rest do not map to a domain event this service publishes** and
are called directly by the code that observes the underlying fact:
Maintenance Scheduled (`MaintenanceService.schedule`), Security Event
(`SecurityEventService.record`), Health Degradation/Platform Issue (the
health sweep worker, and via `PlatformHealthChanged`'s payload).

**License Expiration is a declared integration point, not
internally triggered.** This service holds no license data of its own
(that is `services/license-billing-service`'s system of record, per
docs/070's own PLATFORM INTEGRATIONS section) -- the method exists for
that integration to call, but nothing in this service's own workers or
routes calls it, since there is no local fact to source the trigger
from.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_MAINTENANCE_SCHEDULED = "administration_portal.maintenance_scheduled"
TOPIC_TENANT_PROVISIONED = "administration_portal.tenant_provisioned"
TOPIC_PLATFORM_ISSUE = "administration_portal.platform_issue"
TOPIC_SECURITY_EVENT = "administration_portal.security_event"
TOPIC_LICENSE_EXPIRATION = "administration_portal.license_expiration"
TOPIC_FEATURE_ENABLED = "administration_portal.feature_enabled"
TOPIC_CONFIGURATION_CHANGED = "administration_portal.configuration_changed"
TOPIC_HEALTH_DEGRADATION = "administration_portal.health_degradation"

_UNHEALTHY_STATUSES = frozenset({"unhealthy"})
_DEGRADED_STATUSES = frozenset({"degraded"})


class AdminNotifier:
    """Sends the eight notification kinds docs/070 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_maintenance_scheduled(
        self, *, maintenance_window_id: str, starts_at: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_MAINTENANCE_SCHEDULED,
            notification_type=NotificationType.INFORMATION,
            body=(
                f"Maintenance window {maintenance_window_id} is scheduled to start at "
                f"{starts_at}."
            ),
            priority=Priority.NORMAL,
            variables={"maintenance_window_id": maintenance_window_id},
        )

    async def notify_tenant_provisioned(self, *, tenant_id: str, name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_TENANT_PROVISIONED,
            notification_type=NotificationType.INFORMATION,
            body=f"Tenant {name!r} ({tenant_id}) has been provisioned.",
            priority=Priority.NORMAL,
            variables={"tenant_id": tenant_id},
        )

    async def notify_platform_issue(self, *, component: str, status: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PLATFORM_ISSUE,
            notification_type=NotificationType.MONITORING,
            body=f"Platform component {component!r} is {status}.",
            priority=Priority.CRITICAL,
            variables={"component": component},
        )

    async def notify_security_event(
        self, *, security_event_id: str, kind: str, severity: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SECURITY_EVENT,
            notification_type=NotificationType.WARNING,
            body=f"Security event {kind} detected at {severity} severity.",
            priority=Priority.HIGH,
            variables={"security_event_id": security_event_id},
        )

    async def notify_license_expiration(self, *, customer_id: str, days_remaining: int) -> None:
        await self._manager.broadcast(
            topic=TOPIC_LICENSE_EXPIRATION,
            notification_type=NotificationType.WARNING,
            body=f"A license for customer {customer_id} expires in {days_remaining} day(s).",
            priority=Priority.HIGH,
            variables={"customer_id": customer_id},
        )

    async def notify_feature_enabled(self, *, feature_flag_id: str, name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_FEATURE_ENABLED,
            notification_type=NotificationType.INFORMATION,
            body=f"Feature flag {name!r} was updated.",
            priority=Priority.NORMAL,
            variables={"feature_flag_id": feature_flag_id},
        )

    async def notify_configuration_changed(self, *, key: str, environment: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CONFIGURATION_CHANGED,
            notification_type=NotificationType.INFORMATION,
            body=f"Configuration {key!r} changed for environment {environment!r}.",
            priority=Priority.NORMAL,
            variables={"key": key},
        )

    async def notify_health_degradation(self, *, component: str, status: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_HEALTH_DEGRADATION,
            notification_type=NotificationType.WARNING,
            body=f"Platform component {component!r} degraded to {status}.",
            priority=Priority.HIGH,
            variables={"component": component},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: AdminNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "TenantCreated":
            await self._notifier.notify_tenant_provisioned(
                tenant_id=str(payload.get("tenant_id", "")), name=str(payload.get("name", ""))
            )
        elif event.event_name == "ConfigurationChanged":
            await self._notifier.notify_configuration_changed(
                key=str(payload.get("key", "")), environment=str(payload.get("environment", ""))
            )
        elif event.event_name == "FeatureFlagUpdated":
            await self._notifier.notify_feature_enabled(
                feature_flag_id=str(payload.get("feature_flag_id", "")),
                name=str(payload.get("name", "")),
            )
        elif event.event_name == "PlatformHealthChanged":
            status = str(payload.get("status", ""))
            component = str(payload.get("component", ""))
            if status in _UNHEALTHY_STATUSES:
                await self._notifier.notify_platform_issue(component=component, status=status)
            elif status in _DEGRADED_STATUSES:
                await self._notifier.notify_health_degradation(component=component, status=status)


__all__ = ["AdminNotifier", "NotifyingPublisher"]
