"""Notifications (docs/078 "NOTIFICATIONS", integrating Prompt 025).

**One of the seven notification kinds has a domain event behind it**
(Performance Regression, fanned from ``RegressionDetected``) and is
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Six kinds are called directly** by the code that observes the
underlying fact: Capacity Warning (the capacity threshold sweep
worker, edge-triggered), SLO Violation (the SLO compliance sweep
worker, edge-triggered), Benchmark Completed (the benchmark run
service, on every terminal state), Optimization Available (the
optimization recommendation service, for every non-scaling category),
Infrastructure Bottleneck (the resource utilization service,
synchronously on a bottleneck-level sample), Scaling Recommendation
(the optimization recommendation service, specifically for the
scaling category).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_PERFORMANCE_REGRESSION = "performance_benchmark_framework.performance_regression"
TOPIC_CAPACITY_WARNING = "performance_benchmark_framework.capacity_warning"
TOPIC_SLO_VIOLATION = "performance_benchmark_framework.slo_violation"
TOPIC_BENCHMARK_COMPLETED = "performance_benchmark_framework.benchmark_completed"
TOPIC_OPTIMIZATION_AVAILABLE = "performance_benchmark_framework.optimization_available"
TOPIC_INFRASTRUCTURE_BOTTLENECK = "performance_benchmark_framework.infrastructure_bottleneck"
TOPIC_SCALING_RECOMMENDATION = "performance_benchmark_framework.scaling_recommendation"


class BenchmarkNotifier:
    """Sends the seven notification kinds docs/078 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_performance_regression(self, *, metric_name: str, severity: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PERFORMANCE_REGRESSION,
            notification_type=NotificationType.ERROR,
            body=f"Performance regression detected in {metric_name!r} ({severity}).",
            priority=Priority.HIGH,
            variables={"metric_name": metric_name, "severity": severity},
        )

    async def notify_capacity_warning(
        self, *, resource_name: str, projected_value: float, threshold_value: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CAPACITY_WARNING,
            notification_type=NotificationType.WARNING,
            body=(
                f"Capacity forecast for {resource_name!r} reached its threshold "
                f"({projected_value:.1f} >= {threshold_value:.1f})."
            ),
            priority=Priority.HIGH,
            variables={
                "resource_name": resource_name,
                "projected_value": projected_value,
                "threshold_value": threshold_value,
            },
        )

    async def notify_slo_violation(
        self, *, slo_name: str, actual_value: float, target_value: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SLO_VIOLATION,
            notification_type=NotificationType.ERROR,
            body=(
                f"SLO {slo_name!r} is out of compliance "
                f"({actual_value:.2f} vs target {target_value:.2f})."
            ),
            priority=Priority.HIGH,
            variables={
                "slo_name": slo_name,
                "actual_value": actual_value,
                "target_value": target_value,
            },
        )

    async def notify_benchmark_completed(self, *, benchmark_suite_name: str, status: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_BENCHMARK_COMPLETED,
            notification_type=NotificationType.INFORMATION,
            body=f"Benchmark suite {benchmark_suite_name!r} run completed: {status}.",
            priority=Priority.NORMAL,
            variables={"benchmark_suite_name": benchmark_suite_name, "status": status},
        )

    async def notify_optimization_available(self, *, title: str, impact_score: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_OPTIMIZATION_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=(
                f"New optimization recommendation available: {title!r} "
                f"(impact {impact_score:.1f})."
            ),
            priority=Priority.NORMAL,
            variables={"title": title, "impact_score": impact_score},
        )

    async def notify_infrastructure_bottleneck(
        self, *, resource_type: str, utilization_percent: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_INFRASTRUCTURE_BOTTLENECK,
            notification_type=NotificationType.WARNING,
            body=(
                f"{resource_type} utilization reached a bottleneck level "
                f"({utilization_percent:.1f}%)."
            ),
            priority=Priority.HIGH,
            variables={"resource_type": resource_type, "utilization_percent": utilization_percent},
        )

    async def notify_scaling_recommendation(self, *, title: str, impact_score: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SCALING_RECOMMENDATION,
            notification_type=NotificationType.INFORMATION,
            body=f"New scaling recommendation available: {title!r} (impact {impact_score:.1f}).",
            priority=Priority.NORMAL,
            variables={"title": title, "impact_score": impact_score},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: BenchmarkNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "RegressionDetected":
            await self._notifier.notify_performance_regression(
                metric_name=str(payload.get("metric_name", "")),
                severity=str(payload.get("severity", "")),
            )


__all__ = ["BenchmarkNotifier", "NotifyingPublisher"]
