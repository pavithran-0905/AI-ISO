"""Notifications (docs/080 "NOTIFICATIONS", integrating Prompt 025).

**One of the eight notification kinds has a domain event behind it**
(Security Release, fanned from ``ReleasePublished`` -- but only when
the published version's own ``is_security_release`` flag is set) and
is dispatched by :class:`NotifyingPublisher`, an ``EventPublisher``
that wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Seven kinds are called directly** by the code that observes the
underlying fact: New Release (the release version service, on every
creation), LTS Release (the LTS version service, when a release
version is first designated as an LTS line), Promotion Complete (the
promotion service, on a completed promotion), Release Failure (the
build service, on a failed terminal state), EOL Warning (the LTS
support expiry and EOL schedule sweep workers, both edge-triggered),
Patch Available (the release version service, on publishing a
*subsequent* LTS-channel release), Critical Update (the release
version service, on publishing a security release specifically on the
``STABLE``/``LTS`` channels -- the strongest "you must update now"
combination).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_NEW_RELEASE = "release_distribution_framework.new_release"
TOPIC_SECURITY_RELEASE = "release_distribution_framework.security_release"
TOPIC_LTS_RELEASE = "release_distribution_framework.lts_release"
TOPIC_PROMOTION_COMPLETE = "release_distribution_framework.promotion_complete"
TOPIC_RELEASE_FAILURE = "release_distribution_framework.release_failure"
TOPIC_EOL_WARNING = "release_distribution_framework.eol_warning"
TOPIC_PATCH_AVAILABLE = "release_distribution_framework.patch_available"
TOPIC_CRITICAL_UPDATE = "release_distribution_framework.critical_update"


class ReleaseNotifier:
    """Sends the eight notification kinds docs/080 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_new_release(self, *, version_label: str, channel_type: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_NEW_RELEASE,
            notification_type=NotificationType.INFORMATION,
            body=f"New release {version_label!r} created on channel {channel_type!r}.",
            priority=Priority.NORMAL,
            variables={"version_label": version_label, "channel_type": channel_type},
        )

    async def notify_security_release(self, *, version_label: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SECURITY_RELEASE,
            notification_type=NotificationType.SECURITY,
            body=f"Security release {version_label!r} has been published.",
            priority=Priority.HIGH,
            variables={"version_label": version_label},
        )

    async def notify_lts_release(self, *, version_label: str, support_ends_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_LTS_RELEASE,
            notification_type=NotificationType.INFORMATION,
            body=f"New LTS release {version_label!r} is supported until {support_ends_at}.",
            priority=Priority.NORMAL,
            variables={"version_label": version_label, "support_ends_at": support_ends_at},
        )

    async def notify_promotion_complete(self, *, version_label: str, to_channel: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PROMOTION_COMPLETE,
            notification_type=NotificationType.SUCCESS,
            body=f"Release {version_label!r} was promoted to {to_channel!r}.",
            priority=Priority.NORMAL,
            variables={"version_label": version_label, "to_channel": to_channel},
        )

    async def notify_release_failure(self, *, version_label: str, error_message: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_RELEASE_FAILURE,
            notification_type=NotificationType.ERROR,
            body=f"Release build for {version_label!r} failed: {error_message}",
            priority=Priority.HIGH,
            variables={"version_label": version_label, "error_message": error_message},
        )

    async def notify_eol_warning(self, *, version_label: str, eol_date: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_EOL_WARNING,
            notification_type=NotificationType.WARNING,
            body=f"Release {version_label!r} reaches end of life on {eol_date}.",
            priority=Priority.HIGH,
            variables={"version_label": version_label, "eol_date": eol_date},
        )

    async def notify_patch_available(self, *, version_label: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PATCH_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"Patch {version_label!r} is now available for your LTS line.",
            priority=Priority.NORMAL,
            variables={"version_label": version_label},
        )

    async def notify_critical_update(self, *, version_label: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CRITICAL_UPDATE,
            notification_type=NotificationType.CRITICAL,
            body=f"Critical update {version_label!r} must be applied as soon as possible.",
            priority=Priority.CRITICAL,
            variables={"version_label": version_label},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: ReleaseNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "ReleasePublished" and payload.get("is_security_release"):
            await self._notifier.notify_security_release(
                version_label=str(payload.get("version_label", ""))
            )


__all__ = ["NotifyingPublisher", "ReleaseNotifier"]
