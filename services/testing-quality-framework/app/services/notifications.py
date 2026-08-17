"""Notifications (docs/077 "NOTIFICATIONS", integrating Prompt 025).

**One of the seven notification kinds has a domain event behind it**
(Quality Gate Failed, fanned from ``QualityGateFailed``) and is
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Six kinds are called directly** by the code that observes the
underlying fact: Pipeline Failed (the pipeline service, on its own
failure, and the pipeline timeout sweep worker), Coverage Dropped (the
coverage drop sweep worker, edge-triggered), Performance Regression
(the performance service, on detecting a regression against baseline),
Security Issue (the security service, on a non-``PASSED``
classification), Flaky Test Detected (the flaky test detection
worker, edge-triggered), Benchmark Regression (the benchmark service,
on detecting a regression against baseline).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_PIPELINE_FAILED = "testing_quality_framework.pipeline_failed"
TOPIC_COVERAGE_DROPPED = "testing_quality_framework.coverage_dropped"
TOPIC_PERFORMANCE_REGRESSION = "testing_quality_framework.performance_regression"
TOPIC_SECURITY_ISSUE = "testing_quality_framework.security_issue"
TOPIC_QUALITY_GATE_FAILED = "testing_quality_framework.quality_gate_failed"
TOPIC_FLAKY_TEST_DETECTED = "testing_quality_framework.flaky_test_detected"
TOPIC_BENCHMARK_REGRESSION = "testing_quality_framework.benchmark_regression"


class QaNotifier:
    """Sends the seven notification kinds docs/077 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_pipeline_failed(self, *, pipeline_name: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PIPELINE_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Pipeline {pipeline_name!r} failed: {reason}",
            priority=Priority.HIGH,
            variables={"pipeline_name": pipeline_name, "reason": reason},
        )

    async def notify_coverage_dropped(
        self, *, coverage_type: str, current: float, previous: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_COVERAGE_DROPPED,
            notification_type=NotificationType.WARNING,
            body=f"{coverage_type} coverage dropped from {previous:.1f}% to {current:.1f}%.",
            priority=Priority.HIGH,
            variables={"coverage_type": coverage_type, "current": current, "previous": previous},
        )

    async def notify_performance_regression(self, *, performance_type: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PERFORMANCE_REGRESSION,
            notification_type=NotificationType.WARNING,
            body=f"Performance regression detected ({performance_type}): {detail}",
            priority=Priority.HIGH,
            variables={"performance_type": performance_type, "detail": detail},
        )

    async def notify_security_issue(self, *, security_type: str, findings_count: int) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SECURITY_ISSUE,
            notification_type=NotificationType.ERROR,
            body=f"Security issue detected ({security_type}): {findings_count} finding(s).",
            priority=Priority.HIGH,
            variables={"security_type": security_type, "findings_count": findings_count},
        )

    async def notify_quality_gate_failed(self, *, gate_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_QUALITY_GATE_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Quality gate {gate_name!r} failed.",
            priority=Priority.HIGH,
            variables={"gate_name": gate_name},
        )

    async def notify_flaky_test_detected(self, *, test_case_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_FLAKY_TEST_DETECTED,
            notification_type=NotificationType.WARNING,
            body=f"Flaky test detected: {test_case_name!r}.",
            priority=Priority.NORMAL,
            variables={"test_case_name": test_case_name},
        )

    async def notify_benchmark_regression(self, *, benchmark_name: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_BENCHMARK_REGRESSION,
            notification_type=NotificationType.WARNING,
            body=f"Benchmark regression detected ({benchmark_name}): {detail}",
            priority=Priority.HIGH,
            variables={"benchmark_name": benchmark_name, "detail": detail},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: QaNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "QualityGateFailed":
            await self._notifier.notify_quality_gate_failed(
                gate_name=str(payload.get("gate_type", ""))
            )


__all__ = ["NotifyingPublisher", "QaNotifier"]
