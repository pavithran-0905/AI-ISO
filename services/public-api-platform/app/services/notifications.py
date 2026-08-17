"""Notifications (docs/073 "NOTIFICATIONS", integrating Prompt 025).

**One of the seven notification kinds has a domain event behind it**
(API Version Released) and is dispatched by :class:`NotifyingPublisher`,
an ``EventPublisher`` that wraps the real one, forwards every event
unchanged, and opportunistically notifies for the subset that warrant
it -- exactly the pattern ``services/mobile-api-service`` established.

**Five kinds are called directly** by the code that observes the
underlying fact: Developer Approved and Application Approved (their
own services, on the ``-> ACTIVE`` transition), Quota Warning (the
quota reset sweep worker, within its own warning threshold), and
Deprecation Notice and Credential Expiring (their own sweep workers,
within their own warning windows).

**Webhook Failure is a declared seam.** This service does not own any
webhook data -- ``services/webhook-service`` (Prompt 057) does, and its
own retry/analytics loop is where a real webhook-failure signal
originates. This method exists and is directly tested like every other
notification, but nothing inside this build calls it: a full deployment
would wire it to whatever consumes webhook-service's own failure
events, which is out of this service's scope per docs/073's own
"Integrate Webhook Service (057)" instruction -- integrate, not
reimplement.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_DEVELOPER_APPROVED = "public_api_platform.developer_approved"
TOPIC_APPLICATION_APPROVED = "public_api_platform.application_approved"
TOPIC_API_VERSION_RELEASED = "public_api_platform.api_version_released"
TOPIC_QUOTA_WARNING = "public_api_platform.quota_warning"
TOPIC_DEPRECATION_NOTICE = "public_api_platform.deprecation_notice"
TOPIC_CREDENTIAL_EXPIRING = "public_api_platform.credential_expiring"
TOPIC_WEBHOOK_FAILURE = "public_api_platform.webhook_failure"


class DeveloperNotifier:
    """Sends the seven notification kinds docs/073 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_developer_approved(self, *, email: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DEVELOPER_APPROVED,
            notification_type=NotificationType.INFORMATION,
            body=f"Your developer account ({email}) has been approved.",
            priority=Priority.NORMAL,
            variables={"email": email},
        )

    async def notify_application_approved(self, *, application_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_APPLICATION_APPROVED,
            notification_type=NotificationType.INFORMATION,
            body=f"Your application {application_name!r} has been approved.",
            priority=Priority.NORMAL,
            variables={"application_name": application_name},
        )

    async def notify_api_version_released(self, *, product_name: str, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_API_VERSION_RELEASED,
            notification_type=NotificationType.INFORMATION,
            body=f"{product_name} version {version} has been released.",
            priority=Priority.NORMAL,
            variables={"product_name": product_name, "version": version},
        )

    async def notify_quota_warning(self, *, quota_type: str, used_percent: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_QUOTA_WARNING,
            notification_type=NotificationType.WARNING,
            body=f"Your {quota_type} quota is at {used_percent:.0f}% of its own limit.",
            priority=Priority.HIGH,
            variables={"quota_type": quota_type},
        )

    async def notify_deprecation_notice(self, *, product_name: str, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DEPRECATION_NOTICE,
            notification_type=NotificationType.WARNING,
            body=f"{product_name} version {version} is now deprecated.",
            priority=Priority.HIGH,
            variables={"product_name": product_name, "version": version},
        )

    async def notify_credential_expiring(self, *, credential_kind: str, expires_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CREDENTIAL_EXPIRING,
            notification_type=NotificationType.WARNING,
            body=f"Your {credential_kind} expires at {expires_at}.",
            priority=Priority.HIGH,
            variables={"credential_kind": credential_kind, "expires_at": expires_at},
        )

    async def notify_webhook_failure(self, *, webhook_url: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_WEBHOOK_FAILURE,
            notification_type=NotificationType.WARNING,
            body=f"Webhook delivery to {webhook_url!r} failed: {reason}",
            priority=Priority.HIGH,
            variables={"webhook_url": webhook_url, "reason": reason},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: DeveloperNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "APIVersionReleased":
            await self._notifier.notify_api_version_released(
                product_name=str(payload.get("product_name", "")),
                version=str(payload.get("version", "")),
            )


__all__ = ["DeveloperNotifier", "NotifyingPublisher"]
