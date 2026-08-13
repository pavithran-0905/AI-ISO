"""Notifications (docs/064 "NOTIFICATIONS", integrating Prompt 025).

Two entry points, for the two ways an alert-worthy fact arises here:

**Four notification kinds have a domain event behind them** (SLO
Violation, Anomaly Detected, Capacity Warning, Root Cause Completed) and
are dispatched by :class:`NotifyingPublisher`, an :class:`EventPublisher`
that wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it. Any service
already wired to publish domain events gets notifications for free by
swapping in this wrapper -- no separate call to remember at every
detection or breach.

**Two do not** (Storage Threshold Reached, Service Degradation): neither
maps to a domain event this service publishes, because a storage
statistic and a topology node's health are read continuously by a
worker, not announced as discrete facts. Those two are called directly.

Every method broadcasts to a topic rather than addressing one user id:
who should hear about an SLO breach is a subscription the operators of
that service configure, not a decision this service can make correctly.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_SLO_VIOLATION = "observability.slo_violation"
TOPIC_ANOMALY_DETECTED = "observability.anomaly_detected"
TOPIC_STORAGE_THRESHOLD = "observability.storage_threshold"
TOPIC_CAPACITY_WARNING = "observability.capacity_warning"
TOPIC_ROOT_CAUSE_COMPLETED = "observability.root_cause_completed"
TOPIC_SERVICE_DEGRADATION = "observability.service_degradation"

_WARNING_QUALITIES = frozenset({"unreliable", "insufficient"})
_URGENT_EXHAUSTION_DAYS = 14.0
"""Under two weeks to exhaustion is a capacity warning worth a
notification; a forecast projecting six months out is a dashboard fact,
not a page."""


class ObservabilityNotifier:
    """Sends the six notification kinds docs/064 names, over the shared
    notification framework's broadcast-to-topic mechanism."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_slo_violation(
        self, *, slo_name: str, service_name: str, status: str, value: float | None
    ) -> None:
        formatted = f"{value:.4f}" if value is not None else "no data"
        await self._manager.broadcast(
            topic=TOPIC_SLO_VIOLATION,
            notification_type=NotificationType.MONITORING,
            body=f"SLO '{slo_name}' for {service_name} is {status} (value: {formatted}).",
            priority=Priority.CRITICAL if status == "exhausted" else Priority.HIGH,
            variables={"slo_name": slo_name, "service_name": service_name, "status": status},
        )

    async def notify_anomaly_detected(
        self, *, service_name: str | None, severity: str, method: str, rationale: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_ANOMALY_DETECTED,
            notification_type=NotificationType.MONITORING,
            body=f"Anomaly ({severity}) detected on {service_name or 'unknown service'}: "
            f"{rationale}",
            priority=Priority.CRITICAL if severity == "critical" else Priority.HIGH,
            variables={"service_name": service_name, "severity": severity, "method": method},
        )

    async def notify_storage_threshold_reached(
        self, *, resource: str, used_fraction: float, threshold_fraction: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_STORAGE_THRESHOLD,
            notification_type=NotificationType.WARNING,
            body=f"{resource} storage is at {used_fraction:.0%}, past the "
            f"{threshold_fraction:.0%} threshold.",
            priority=Priority.HIGH,
            variables={"resource": resource, "used_fraction": used_fraction},
        )

    async def notify_capacity_warning(
        self, *, resource_kind: str, quality: str, days_until_exhaustion: float | None
    ) -> None:
        if days_until_exhaustion is not None:
            body = (
                f"{resource_kind} capacity forecast: {days_until_exhaustion:.1f} "
                "days to exhaustion."
            )
            priority = (
                Priority.CRITICAL
                if days_until_exhaustion <= _URGENT_EXHAUSTION_DAYS
                else Priority.NORMAL
            )
        else:
            body = (
                f"{resource_kind} capacity forecast quality is {quality}: "
                "no reliable projection."
            )
            priority = Priority.NORMAL
        await self._manager.broadcast(
            topic=TOPIC_CAPACITY_WARNING,
            notification_type=NotificationType.MONITORING,
            body=body,
            priority=priority,
            variables={"resource_kind": resource_kind, "quality": quality},
        )

    async def notify_root_cause_completed(
        self, *, service_name: str, is_conclusive: bool, top_candidate_service: str | None
    ) -> None:
        body = (
            f"Root cause analysis for {service_name} points to {top_candidate_service}."
            if is_conclusive and top_candidate_service
            else f"Root cause analysis for {service_name} finished without a conclusive cause."
        )
        await self._manager.broadcast(
            topic=TOPIC_ROOT_CAUSE_COMPLETED,
            notification_type=NotificationType.INFORMATION,
            body=body,
            priority=Priority.NORMAL,
            variables={"service_name": service_name, "is_conclusive": is_conclusive},
        )

    async def notify_service_degradation(
        self, *, service_name: str, environment: str, health: str, reason: str | None
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SERVICE_DEGRADATION,
            notification_type=NotificationType.MONITORING,
            body=f"{service_name} ({environment}) is {health}" + (f": {reason}" if reason else "."),
            priority=Priority.HIGH,
            variables={"service_name": service_name, "environment": environment, "health": health},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination (the queue, the audit trail)
    exactly as if this wrapper were not there. Notification is a
    best-effort side channel on top of publishing, not a gate on it.
    """

    def __init__(self, inner: EventPublisher, notifier: ObservabilityNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "SLOBreached":
            await self._notifier.notify_slo_violation(
                slo_name=str(payload.get("slo_name") or payload.get("slo_id", "")),
                service_name=str(payload.get("service_name") or "unknown service"),
                status=str(payload.get("status", "")),
                value=payload.get("value"),
            )
        elif event.event_name == "AnomalyDetected":
            await self._notifier.notify_anomaly_detected(
                service_name=payload.get("service_name"),
                severity=str(payload.get("severity", "")),
                method=str(payload.get("method", "")),
                rationale=(
                    f"deviation {payload['deviation']:+.2f}"
                    if payload.get("deviation") is not None
                    else "no measured deviation"
                ),
            )
        elif event.event_name == "CapacityForecastGenerated":
            quality = str(payload.get("quality", ""))
            days = payload.get("days_until_exhaustion")
            if quality in _WARNING_QUALITIES or (
                days is not None and days <= _URGENT_EXHAUSTION_DAYS
            ):
                await self._notifier.notify_capacity_warning(
                    resource_kind=str(payload.get("resource_kind", "")),
                    quality=quality,
                    days_until_exhaustion=days,
                )
        elif event.event_name == "RootCauseCompleted":
            await self._notifier.notify_root_cause_completed(
                service_name=str(payload.get("service_name", "")),
                is_conclusive=bool(payload.get("is_conclusive", False)),
                top_candidate_service=payload.get("top_candidate_service"),
            )


__all__ = [
    "TOPIC_ANOMALY_DETECTED",
    "TOPIC_CAPACITY_WARNING",
    "TOPIC_ROOT_CAUSE_COMPLETED",
    "TOPIC_SERVICE_DEGRADATION",
    "TOPIC_SLO_VIOLATION",
    "TOPIC_STORAGE_THRESHOLD",
    "NotifyingPublisher",
    "ObservabilityNotifier",
]
