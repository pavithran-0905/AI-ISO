"""Notifications (docs/076 "NOTIFICATIONS", integrating Prompt 025).

**One of the seven notification kinds has a domain event behind it**
(Release Published, fanned from ``ReleasePublished``) and is
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Six kinds are called directly** by the code that observes the
underlying fact: Upgrade Available (the release adoption sweep worker,
edge-triggered), Upgrade Scheduled (the upgrade service, on its own
plan-to-job scheduling step), Upgrade Failed (the upgrade service and
both the job timeout sweep and health gate enforcement workers),
Rollback Completed (the rollback service, on its own completion),
Compatibility Issue (the compatibility service, on a non-``PASSED``
classification), Migration Failed (the migration service, on a
``FAILED`` migration step).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_UPGRADE_AVAILABLE = "upgrade_framework.upgrade_available"
TOPIC_UPGRADE_SCHEDULED = "upgrade_framework.upgrade_scheduled"
TOPIC_UPGRADE_FAILED = "upgrade_framework.upgrade_failed"
TOPIC_ROLLBACK_COMPLETED = "upgrade_framework.rollback_completed"
TOPIC_COMPATIBILITY_ISSUE = "upgrade_framework.compatibility_issue"
TOPIC_MIGRATION_FAILED = "upgrade_framework.migration_failed"
TOPIC_RELEASE_PUBLISHED = "upgrade_framework.release_published"


class UpgradeNotifier:
    """Sends the seven notification kinds docs/076 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_upgrade_available(self, *, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_UPGRADE_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"A new platform version ({version}) is available.",
            priority=Priority.NORMAL,
            variables={"version": version},
        )

    async def notify_upgrade_scheduled(self, *, plan_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_UPGRADE_SCHEDULED,
            notification_type=NotificationType.INFORMATION,
            body=f"Upgrade plan {plan_name!r} has been scheduled.",
            priority=Priority.NORMAL,
            variables={"plan_name": plan_name},
        )

    async def notify_upgrade_failed(self, *, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_UPGRADE_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Upgrade failed: {reason}",
            priority=Priority.HIGH,
            variables={"reason": reason},
        )

    async def notify_rollback_completed(self, *, to_version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_ROLLBACK_COMPLETED,
            notification_type=NotificationType.INFORMATION,
            body=f"Rollback to {to_version} completed.",
            priority=Priority.NORMAL,
            variables={"to_version": to_version},
        )

    async def notify_compatibility_issue(self, *, compatibility_type: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_COMPATIBILITY_ISSUE,
            notification_type=NotificationType.WARNING,
            body=f"Compatibility issue ({compatibility_type}): {detail}",
            priority=Priority.HIGH,
            variables={"compatibility_type": compatibility_type, "detail": detail},
        )

    async def notify_migration_failed(self, *, migration_type: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_MIGRATION_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Migration ({migration_type}) failed: {detail}",
            priority=Priority.HIGH,
            variables={"migration_type": migration_type, "detail": detail},
        )

    async def notify_release_published(self, *, version_label: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_RELEASE_PUBLISHED,
            notification_type=NotificationType.INFORMATION,
            body=f"Release {version_label} has been published.",
            priority=Priority.NORMAL,
            variables={"version_label": version_label},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: UpgradeNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "ReleasePublished":
            await self._notifier.notify_release_published(
                version_label=str(payload.get("version_label", ""))
            )


__all__ = ["NotifyingPublisher", "UpgradeNotifier"]
