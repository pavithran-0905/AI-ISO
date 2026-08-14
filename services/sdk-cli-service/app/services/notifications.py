"""Notifications (docs/071 "NOTIFICATIONS", integrating Prompt 025).

**One of the six notification kinds has a domain event behind it**
(New SDK Release) and is dispatched by :class:`NotifyingPublisher`, an
``EventPublisher`` that wraps the real one, forwards every event
unchanged, and opportunistically notifies for the subset that warrant
it -- exactly the pattern
``services/administration-portal-service/app/services/notifications.py``
established. A release carrying ``breaking_changes=True`` in its own
payload additionally fans out to Breaking API Changes.

**The rest do not map to a domain event this service publishes** and
are called directly by the code that observes the underlying fact: CLI
Update Available and Plugin Update Available (their own sweep
workers), Authentication Failure (the session service, on a failed
attempt), and Deprecation Notices (the version compatibility sweep
worker, when a version crosses into its own warning window).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_NEW_SDK_RELEASE = "sdk_cli.new_sdk_release"
TOPIC_CLI_UPDATE_AVAILABLE = "sdk_cli.cli_update_available"
TOPIC_PLUGIN_UPDATE_AVAILABLE = "sdk_cli.plugin_update_available"
TOPIC_AUTHENTICATION_FAILURE = "sdk_cli.authentication_failure"
TOPIC_BREAKING_API_CHANGES = "sdk_cli.breaking_api_changes"
TOPIC_DEPRECATION_NOTICE = "sdk_cli.deprecation_notice"


class SdkCliNotifier:
    """Sends the six notification kinds docs/071 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_new_sdk_release(self, *, language: str, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_NEW_SDK_RELEASE,
            notification_type=NotificationType.INFORMATION,
            body=f"A new {language} SDK release ({version}) is available.",
            priority=Priority.NORMAL,
            variables={"language": language, "version": version},
        )

    async def notify_cli_update_available(
        self, *, current_version: str, latest_version: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CLI_UPDATE_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"CLI {latest_version} is available (currently on {current_version}).",
            priority=Priority.NORMAL,
            variables={"current_version": current_version, "latest_version": latest_version},
        )

    async def notify_plugin_update_available(
        self, *, plugin_name: str, latest_version: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PLUGIN_UPDATE_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"Plugin {plugin_name!r} has an update available ({latest_version}).",
            priority=Priority.NORMAL,
            variables={"plugin_name": plugin_name},
        )

    async def notify_authentication_failure(self, *, profile_name: str, auth_method: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_AUTHENTICATION_FAILURE,
            notification_type=NotificationType.WARNING,
            body=f"Authentication failed for profile {profile_name!r} via {auth_method}.",
            priority=Priority.HIGH,
            variables={"profile_name": profile_name},
        )

    async def notify_breaking_api_changes(self, *, language: str, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_BREAKING_API_CHANGES,
            notification_type=NotificationType.WARNING,
            body=f"{language} SDK {version} contains breaking API changes.",
            priority=Priority.HIGH,
            variables={"language": language, "version": version},
        )

    async def notify_deprecation_notice(
        self, *, kind: str, version: str, deprecated_at: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DEPRECATION_NOTICE,
            notification_type=NotificationType.WARNING,
            body=f"{kind} version {version} is deprecated as of {deprecated_at}.",
            priority=Priority.HIGH,
            variables={"kind": kind, "version": version},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: SdkCliNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "SDKReleased":
            language = str(payload.get("language", ""))
            version = str(payload.get("version", ""))
            await self._notifier.notify_new_sdk_release(language=language, version=version)
            if bool(payload.get("breaking_changes", False)):
                await self._notifier.notify_breaking_api_changes(language=language, version=version)


__all__ = ["NotifyingPublisher", "SdkCliNotifier"]
