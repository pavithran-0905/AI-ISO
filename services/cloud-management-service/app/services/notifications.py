"""Notifications (docs/068 "NOTIFICATIONS", integrating Prompt 025).

**Two of the seven notification kinds have a domain event behind them**
(Budget Exceeded, Cloud Drift Detected) and are dispatched by
:class:`NotifyingPublisher`, an ``EventPublisher`` that wraps the real
one, forwards every event unchanged, and opportunistically notifies for
the subset that warrant it -- exactly the pattern
``services/multi-cluster-management-service/app/services/notifications.py``
established.

**The other five do not** (Idle Resource Detected, Compliance
Violation, Provisioning Failed, Credential Expiring, Optimization
Available): none maps to a lifecycle-boundary domain event this service
publishes as a matching notification, since idle-resource sweeps,
compliance sweeps, and credential-expiry sweeps are observed
continuously by a worker rather than announced as discrete facts. Those
are called directly by the workers that observe them.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_BUDGET_EXCEEDED = "cloud_management.budget_exceeded"
TOPIC_IDLE_RESOURCE_DETECTED = "cloud_management.idle_resource_detected"
TOPIC_COMPLIANCE_VIOLATION = "cloud_management.compliance_violation"
TOPIC_PROVISIONING_FAILED = "cloud_management.provisioning_failed"
TOPIC_CREDENTIAL_EXPIRING = "cloud_management.credential_expiring"
TOPIC_DRIFT_DETECTED = "cloud_management.drift_detected"
TOPIC_OPTIMIZATION_AVAILABLE = "cloud_management.optimization_available"


class CloudNotifier:
    """Sends the seven notification kinds docs/068 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_budget_exceeded(
        self, *, budget_id: str, status: str, current_spend: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_BUDGET_EXCEEDED,
            notification_type=NotificationType.MONITORING,
            body=f"Budget {budget_id} is {status} at {current_spend:.2f}.",
            priority=Priority.CRITICAL,
            variables={"budget_id": budget_id, "status": status},
        )

    async def notify_idle_resource_detected(
        self, *, resource_id: str, utilization_fraction: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_IDLE_RESOURCE_DETECTED,
            notification_type=NotificationType.INFORMATION,
            body=f"Resource {resource_id} is idle at {utilization_fraction:.0%} utilization.",
            priority=Priority.NORMAL,
            variables={"resource_id": resource_id},
        )

    async def notify_compliance_violation(
        self, *, account_id: str, framework: str, status: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_COMPLIANCE_VIOLATION,
            notification_type=NotificationType.WARNING,
            body=f"Account {account_id} is {status} against {framework}.",
            priority=Priority.HIGH,
            variables={"account_id": account_id, "framework": framework},
        )

    async def notify_provisioning_failed(self, *, resource_id: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PROVISIONING_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"Provisioning failed for resource {resource_id}: {detail}",
            priority=Priority.CRITICAL,
            variables={"resource_id": resource_id},
        )

    async def notify_credential_expiring(self, *, account_id: str, expires_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CREDENTIAL_EXPIRING,
            notification_type=NotificationType.WARNING,
            body=f"Account {account_id}'s credential expires at {expires_at}.",
            priority=Priority.HIGH,
            variables={"account_id": account_id, "expires_at": expires_at},
        )

    async def notify_drift_detected(self, *, resource_id: str, severity: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DRIFT_DETECTED,
            notification_type=NotificationType.WARNING,
            body=f"Drift detected on resource {resource_id} (severity: {severity}).",
            priority=Priority.HIGH,
            variables={"resource_id": resource_id, "severity": severity},
        )

    async def notify_optimization_available(
        self, *, account_id: str, idle_resource_count: int
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_OPTIMIZATION_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=f"Account {account_id} has {idle_resource_count} optimization opportunity(ies).",
            priority=Priority.NORMAL,
            variables={"account_id": account_id},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: CloudNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "BudgetThresholdExceeded":
            await self._notifier.notify_budget_exceeded(
                budget_id=str(payload.get("budget_id", "")),
                status=str(payload.get("status", "")),
                current_spend=float(payload.get("current_spend", 0.0)),
            )
        elif event.event_name == "DriftDetected":
            await self._notifier.notify_drift_detected(
                resource_id=str(payload.get("resource_id", "")),
                severity=str(payload.get("severity", "")),
            )


__all__ = ["CloudNotifier", "NotifyingPublisher"]
