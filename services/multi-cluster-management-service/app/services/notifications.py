"""Notifications (docs/066 "NOTIFICATIONS", integrating Prompt 025).

**Two of the seven notification kinds have a domain event behind them**
(Cluster Registered, Upgrade Failed) and are dispatched by
:class:`NotifyingPublisher`, an ``EventPublisher`` that wraps the real
one, forwards every event unchanged, and opportunistically notifies for
the subset that warrant it -- exactly the pattern
``services/backup-dr-service/app/services/notifications.py`` established.

**The other five do not** (Cluster Offline, Policy Violation, Compliance
Failure, Capacity Warning, Maintenance Scheduled): none maps to a domain
event this service publishes, because health staleness, capacity
thresholds, and policy/compliance violations are observed continuously
by a worker rather than announced as discrete lifecycle facts. Those are
called directly by the workers that observe them.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_CLUSTER_OFFLINE = "multi_cluster.cluster_offline"
TOPIC_UPGRADE_FAILED = "multi_cluster.upgrade_failed"
TOPIC_POLICY_VIOLATION = "multi_cluster.policy_violation"
TOPIC_COMPLIANCE_FAILURE = "multi_cluster.compliance_failure"
TOPIC_CAPACITY_WARNING = "multi_cluster.capacity_warning"
TOPIC_CLUSTER_REGISTERED = "multi_cluster.cluster_registered"
TOPIC_MAINTENANCE_SCHEDULED = "multi_cluster.maintenance_scheduled"


class FleetNotifier:
    """Sends the seven notification kinds docs/066 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_cluster_offline(self, *, cluster_id: str, cluster_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CLUSTER_OFFLINE,
            notification_type=NotificationType.MONITORING,
            body=f"Cluster {cluster_name} ({cluster_id}) has stopped reporting and is offline.",
            priority=Priority.CRITICAL,
            variables={"cluster_id": cluster_id, "cluster_name": cluster_name},
        )

    async def notify_upgrade_failed(
        self, *, cluster_id: str, upgrade_id: str, error_message: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_UPGRADE_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"Upgrade {upgrade_id} for cluster {cluster_id} failed: {error_message}",
            priority=Priority.CRITICAL,
            variables={"cluster_id": cluster_id, "upgrade_id": upgrade_id},
        )

    async def notify_policy_violation(
        self, *, cluster_id: str, policy_id: str, policy_name: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_POLICY_VIOLATION,
            notification_type=NotificationType.WARNING,
            body=f"Cluster {cluster_id} has drifted from policy {policy_name} ({policy_id}).",
            priority=Priority.HIGH,
            variables={"cluster_id": cluster_id, "policy_id": policy_id},
        )

    async def notify_compliance_failure(
        self, *, cluster_id: str, framework: str, status: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_COMPLIANCE_FAILURE,
            notification_type=NotificationType.WARNING,
            body=f"Cluster {cluster_id} is {status} against {framework}.",
            priority=Priority.HIGH,
            variables={"cluster_id": cluster_id, "framework": framework},
        )

    async def notify_capacity_warning(
        self, *, cluster_id: str, resource_kind: str, utilization_fraction: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CAPACITY_WARNING,
            notification_type=NotificationType.WARNING,
            body=(
                f"Cluster {cluster_id}'s {resource_kind} is at "
                f"{utilization_fraction:.0%} utilization."
            ),
            priority=Priority.HIGH,
            variables={"cluster_id": cluster_id, "resource_kind": resource_kind},
        )

    async def notify_cluster_registered(self, *, cluster_id: str, cluster_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CLUSTER_REGISTERED,
            notification_type=NotificationType.INFORMATION,
            body=f"Cluster {cluster_name} ({cluster_id}) was registered.",
            priority=Priority.NORMAL,
            variables={"cluster_id": cluster_id, "cluster_name": cluster_name},
        )

    async def notify_maintenance_scheduled(self, *, cluster_id: str, scheduled_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_MAINTENANCE_SCHEDULED,
            notification_type=NotificationType.INFORMATION,
            body=f"Maintenance scheduled for cluster {cluster_id} at {scheduled_at}.",
            priority=Priority.NORMAL,
            variables={"cluster_id": cluster_id, "scheduled_at": scheduled_at},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: FleetNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "ClusterRegistered":
            await self._notifier.notify_cluster_registered(
                cluster_id=str(payload.get("cluster_id", "")),
                cluster_name=str(payload.get("name", "")),
            )
        elif event.event_name == "ClusterUpgraded" and str(payload.get("status", "")) == "failed":
            await self._notifier.notify_upgrade_failed(
                cluster_id=str(payload.get("cluster_id", "")),
                upgrade_id=str(payload.get("upgrade_id", "")),
                error_message="see upgrade record details",
            )


__all__ = ["FleetNotifier", "NotifyingPublisher"]
