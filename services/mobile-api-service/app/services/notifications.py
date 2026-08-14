"""Notifications (docs/072 "NOTIFICATIONS", integrating Prompt 025).

**Two of the seven notification kinds have a domain event behind
them** and are dispatched by :class:`NotifyingPublisher`, an
``EventPublisher`` that wraps the real one, forwards every event
unchanged, and opportunistically notifies for the subset that warrant
it -- exactly the pattern ``services/sdk-cli-service/app/services
/notifications.py`` established:

- ``MobileLoginSucceeded`` fans to New Device Login, but only when the
  event's own payload says ``is_new_device: True``.
- ``SynchronizationFailed`` fans unconditionally to Synchronization
  Failed.

**The rest do not map to a domain event this service publishes** and
are called directly by the code that observes the underlying fact:
Device Revoked (``DeviceService.revoke``), App Update Available and
Forced Upgrade (the app version compliance sweep worker, per device),
Security Alert (wherever device integrity is evaluated), and Session
Expiring (the session expiry sweep worker, within its own warning
window).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_NEW_DEVICE_LOGIN = "mobile_api.new_device_login"
TOPIC_DEVICE_REVOKED = "mobile_api.device_revoked"
TOPIC_APP_UPDATE_AVAILABLE = "mobile_api.app_update_available"
TOPIC_FORCED_UPGRADE = "mobile_api.forced_upgrade"
TOPIC_SYNCHRONIZATION_FAILED = "mobile_api.synchronization_failed"
TOPIC_SECURITY_ALERT = "mobile_api.security_alert"
TOPIC_SESSION_EXPIRING = "mobile_api.session_expiring"


class MobileNotifier:
    """Sends the seven notification kinds docs/072 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_new_device_login(self, *, device_identifier: str, platform: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_NEW_DEVICE_LOGIN,
            notification_type=NotificationType.INFORMATION,
            body=f"A new {platform} device ({device_identifier}) signed in to your account.",
            priority=Priority.HIGH,
            variables={"device_identifier": device_identifier, "platform": platform},
        )

    async def notify_device_revoked(self, *, device_identifier: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DEVICE_REVOKED,
            notification_type=NotificationType.WARNING,
            body=f"Device {device_identifier!r} has been revoked and can no longer sign in.",
            priority=Priority.HIGH,
            variables={"device_identifier": device_identifier},
        )

    async def notify_app_update_available(self, *, platform: str, recommended_version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_APP_UPDATE_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"A new {platform} app version ({recommended_version}) is available.",
            priority=Priority.NORMAL,
            variables={"platform": platform, "recommended_version": recommended_version},
        )

    async def notify_forced_upgrade(self, *, platform: str, minimum_version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_FORCED_UPGRADE,
            notification_type=NotificationType.WARNING,
            body=(
                f"Your {platform} app must be updated to at least {minimum_version} "
                "to keep working."
            ),
            priority=Priority.HIGH,
            variables={"platform": platform, "minimum_version": minimum_version},
        )

    async def notify_synchronization_failed(self, *, device_identifier: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SYNCHRONIZATION_FAILED,
            notification_type=NotificationType.WARNING,
            body=f"Synchronization failed for device {device_identifier!r}: {reason}",
            priority=Priority.HIGH,
            variables={"device_identifier": device_identifier, "reason": reason},
        )

    async def notify_security_alert(self, *, device_identifier: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SECURITY_ALERT,
            notification_type=NotificationType.WARNING,
            body=f"Security alert for device {device_identifier!r}: {reason}",
            priority=Priority.HIGH,
            variables={"device_identifier": device_identifier, "reason": reason},
        )

    async def notify_session_expiring(self, *, device_identifier: str, expires_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SESSION_EXPIRING,
            notification_type=NotificationType.INFORMATION,
            body=f"Your session on device {device_identifier!r} expires at {expires_at}.",
            priority=Priority.NORMAL,
            variables={"device_identifier": device_identifier, "expires_at": expires_at},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: MobileNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "MobileLoginSucceeded" and bool(payload.get("is_new_device", False)):
            await self._notifier.notify_new_device_login(
                device_identifier=str(payload.get("device_identifier", "")),
                platform=str(payload.get("platform", "")),
            )
        elif event.event_name == "SynchronizationFailed":
            await self._notifier.notify_synchronization_failed(
                device_identifier=str(payload.get("device_identifier", "")),
                reason=str(payload.get("reason", "unknown")),
            )


__all__ = ["MobileNotifier", "NotifyingPublisher"]
