"""Notifications (docs/075 "NOTIFICATIONS", integrating Prompt 025).

**One of the eight notification kinds has a domain event behind it**
(Rollback Completed, fanned from ``RollbackCompleted``) and is
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Six kinds are called directly** by the code that observes the
underlying fact: Installation Failed (the installation session service,
on its own failure path, and the session expiry sweep worker on a
timeout), Deployment Failed (the deployment job service and the job
timeout sweep worker), Upgrade Failed (the upgrade service, on a
failed upgrade job), Upgrade Available (the upgrade availability sweep
worker, on detecting a newer known version), Certificate Expiring (the
certificate expiry sweep worker), Validation Failed (the preflight and
verification services, on a ``FAILED`` aggregate outcome).

**Infrastructure Issue is a declared seam**, the same shape
``services/developer-portal-service``'s Security Notice notification
is: this service owns no live infrastructure-monitoring signal of its
own, so nothing in this build calls it internally, but it is directly
tested like every other kind.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_INSTALLATION_FAILED = "installation_deployment.installation_failed"
TOPIC_DEPLOYMENT_FAILED = "installation_deployment.deployment_failed"
TOPIC_UPGRADE_AVAILABLE = "installation_deployment.upgrade_available"
TOPIC_UPGRADE_FAILED = "installation_deployment.upgrade_failed"
TOPIC_ROLLBACK_COMPLETED = "installation_deployment.rollback_completed"
TOPIC_CERTIFICATE_EXPIRING = "installation_deployment.certificate_expiring"
TOPIC_VALIDATION_FAILED = "installation_deployment.validation_failed"
TOPIC_INFRASTRUCTURE_ISSUE = "installation_deployment.infrastructure_issue"


class DeploymentNotifier:
    """Sends the eight notification kinds docs/075 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_installation_failed(self, *, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_INSTALLATION_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Installation failed: {reason}",
            priority=Priority.HIGH,
            variables={"reason": reason},
        )

    async def notify_deployment_failed(self, *, job_type: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DEPLOYMENT_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"{job_type} job failed: {reason}",
            priority=Priority.HIGH,
            variables={"job_type": job_type, "reason": reason},
        )

    async def notify_upgrade_available(self, *, version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_UPGRADE_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"A new platform version ({version}) is available.",
            priority=Priority.NORMAL,
            variables={"version": version},
        )

    async def notify_upgrade_failed(self, *, to_version: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_UPGRADE_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Upgrade to {to_version} failed: {reason}",
            priority=Priority.HIGH,
            variables={"to_version": to_version, "reason": reason},
        )

    async def notify_rollback_completed(self, *, to_version: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_ROLLBACK_COMPLETED,
            notification_type=NotificationType.INFORMATION,
            body=f"Rollback to {to_version} completed.",
            priority=Priority.NORMAL,
            variables={"to_version": to_version},
        )

    async def notify_certificate_expiring(self, *, common_name: str, not_after: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CERTIFICATE_EXPIRING,
            notification_type=NotificationType.WARNING,
            body=f"Certificate {common_name!r} expires at {not_after}.",
            priority=Priority.HIGH,
            variables={"common_name": common_name, "not_after": not_after},
        )

    async def notify_validation_failed(self, *, check_type: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_VALIDATION_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Validation check {check_type!r} failed: {detail}",
            priority=Priority.HIGH,
            variables={"check_type": check_type, "detail": detail},
        )

    async def notify_infrastructure_issue(self, *, message: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_INFRASTRUCTURE_ISSUE,
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

    def __init__(self, inner: EventPublisher, notifier: DeploymentNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "RollbackCompleted":
            await self._notifier.notify_rollback_completed(
                to_version=str(payload.get("to_version", ""))
            )


__all__ = ["DeploymentNotifier", "NotifyingPublisher"]
