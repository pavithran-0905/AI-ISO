"""Notifications (docs/074 "NOTIFICATIONS", integrating Prompt 025).

**One of the eight notification kinds has a domain event behind it**
(Documentation Updated, fanned from ``DocumentationPublished``) and is
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Six kinds are called directly** by the code that observes the
underlying fact: SDK Released (no dedicated event for a *release*, only
for a *download*, so this is called wherever a new SDK version becomes
available to the portal), Plugin Approved and Plugin Rejected (the
plugin review service, on its own reviewer decision), Tutorial
Available (the tutorial service, on its own ``-> PUBLISHED``
transition -- tutorials share ``ContentStatus`` with documentation
pages but have no dedicated publish event of their own), AI
Recommendation (the assistant service, on a confident answer), and
Community Reply (the community service, when a new comment lands on a
post).

**Security Notice is a declared seam**, the same shape
``services/public-api-platform``'s Webhook Failure notification is:
this service owns no security-event detection of its own, so nothing
in this build calls it internally, but it is directly tested like
every other kind.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_DOCUMENTATION_UPDATED = "developer_portal.documentation_updated"
TOPIC_SDK_RELEASED = "developer_portal.sdk_released"
TOPIC_PLUGIN_APPROVED = "developer_portal.plugin_approved"
TOPIC_PLUGIN_REJECTED = "developer_portal.plugin_rejected"
TOPIC_TUTORIAL_AVAILABLE = "developer_portal.tutorial_available"
TOPIC_AI_RECOMMENDATION = "developer_portal.ai_recommendation"
TOPIC_COMMUNITY_REPLY = "developer_portal.community_reply"
TOPIC_SECURITY_NOTICE = "developer_portal.security_notice"


class PortalNotifier:
    """Sends the eight notification kinds docs/074 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_documentation_updated(self, *, title: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DOCUMENTATION_UPDATED,
            notification_type=NotificationType.INFORMATION,
            body=f"Documentation page {title!r} was updated.",
            priority=Priority.NORMAL,
            variables={"title": title},
        )

    async def notify_sdk_released(self, *, language: str, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SDK_RELEASED,
            notification_type=NotificationType.INFORMATION,
            body=f"A new {language} SDK release ({version}) is available.",
            priority=Priority.NORMAL,
            variables={"language": language, "version": version},
        )

    async def notify_plugin_approved(self, *, plugin_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PLUGIN_APPROVED,
            notification_type=NotificationType.INFORMATION,
            body=f"Your plugin {plugin_name!r} has been approved and published.",
            priority=Priority.NORMAL,
            variables={"plugin_name": plugin_name},
        )

    async def notify_plugin_rejected(self, *, plugin_name: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PLUGIN_REJECTED,
            notification_type=NotificationType.WARNING,
            body=f"Your plugin {plugin_name!r} was rejected: {reason}",
            priority=Priority.HIGH,
            variables={"plugin_name": plugin_name, "reason": reason},
        )

    async def notify_tutorial_available(self, *, title: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_TUTORIAL_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"A new tutorial ({title!r}) is now available.",
            priority=Priority.NORMAL,
            variables={"title": title},
        )

    async def notify_ai_recommendation(self, *, title: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_AI_RECOMMENDATION,
            notification_type=NotificationType.INFORMATION,
            body=f"The AI assistant recommends: {title!r}.",
            priority=Priority.NORMAL,
            variables={"title": title},
        )

    async def notify_community_reply(self, *, post_title: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_COMMUNITY_REPLY,
            notification_type=NotificationType.INFORMATION,
            body=f"Someone replied to your post {post_title!r}.",
            priority=Priority.NORMAL,
            variables={"post_title": post_title},
        )

    async def notify_security_notice(self, *, message: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SECURITY_NOTICE,
            notification_type=NotificationType.WARNING,
            body=message,
            priority=Priority.HIGH,
            variables={},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: PortalNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "DocumentationPublished":
            await self._notifier.notify_documentation_updated(title=str(payload.get("title", "")))


__all__ = ["NotifyingPublisher", "PortalNotifier"]
