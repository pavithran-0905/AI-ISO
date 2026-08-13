"""Tests for app.services.notifications -- ObservabilityNotifier and
NotifyingPublisher, against the real shared_core notification framework."""

from __future__ import annotations

from uuid import uuid4

import pytest
from shared_core.notifications.factory import create_notification_framework

from app.events.domain_events import (
    AnomalyDetectedEvent,
    CapacityForecastGeneratedEvent,
    MetricCollectedEvent,
    RootCauseCompletedEvent,
    SloBreachedEvent,
)
from app.services.notifications import (
    NotifyingPublisher,
    ObservabilityNotifier,
)


@pytest.fixture
def manager():
    return create_notification_framework()


@pytest.fixture
def notifier(manager) -> ObservabilityNotifier:
    return ObservabilityNotifier(manager)


class TestObservabilityNotifier:
    async def test_notify_slo_violation(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_slo_violation(
            slo_name="api-availability", service_name="gateway", status="breaching", value=0.95
        )

    async def test_notify_slo_violation_no_data(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_slo_violation(
            slo_name="api-availability", service_name="gateway", status="exhausted", value=None
        )

    async def test_notify_anomaly_detected(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_anomaly_detected(
            service_name="backend", severity="critical", method="robust_zscore", rationale="spike"
        )

    async def test_notify_anomaly_detected_unknown_service(
        self, notifier: ObservabilityNotifier
    ) -> None:
        await notifier.notify_anomaly_detected(
            service_name=None, severity="low", method="threshold", rationale="breach"
        )

    async def test_notify_storage_threshold_reached(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_storage_threshold_reached(
            resource="metrics-db", used_fraction=0.95, threshold_fraction=0.90
        )

    async def test_notify_capacity_warning_with_days(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_capacity_warning(
            resource_kind="disk", quality="good", days_until_exhaustion=5.0
        )

    async def test_notify_capacity_warning_far_out(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_capacity_warning(
            resource_kind="disk", quality="good", days_until_exhaustion=180.0
        )

    async def test_notify_capacity_warning_no_days(self, notifier: ObservabilityNotifier) -> None:
        await notifier.notify_capacity_warning(
            resource_kind="disk", quality="insufficient", days_until_exhaustion=None
        )

    async def test_notify_root_cause_completed_conclusive(
        self, notifier: ObservabilityNotifier
    ) -> None:
        await notifier.notify_root_cause_completed(
            service_name="checkout", is_conclusive=True, top_candidate_service="payments"
        )

    async def test_notify_root_cause_completed_inconclusive(
        self, notifier: ObservabilityNotifier
    ) -> None:
        await notifier.notify_root_cause_completed(
            service_name="checkout", is_conclusive=False, top_candidate_service=None
        )

    async def test_notify_service_degradation_with_reason(
        self, notifier: ObservabilityNotifier
    ) -> None:
        await notifier.notify_service_degradation(
            service_name="backend",
            environment="production",
            health="degraded",
            reason="high error rate",
        )

    async def test_notify_service_degradation_no_reason(
        self, notifier: ObservabilityNotifier
    ) -> None:
        await notifier.notify_service_degradation(
            service_name="backend", environment="production", health="unknown", reason=None
        )


class TestNotifyingPublisher:
    async def _publisher(self, manager) -> tuple[NotifyingPublisher, list]:
        forwarded: list = []

        async def inner(event):
            forwarded.append(event)

        notifier = ObservabilityNotifier(manager)
        return NotifyingPublisher(inner, notifier), forwarded

    async def test_forwards_every_event(self, manager) -> None:
        publisher, forwarded = await self._publisher(manager)
        event = MetricCollectedEvent(
            source_service="test", organization_id=uuid4(), payload={"metric_series_id": "x"}
        )
        await publisher(event)
        assert forwarded == [event]

    async def test_slo_breached_triggers_notification(self, manager) -> None:
        publisher, forwarded = await self._publisher(manager)
        event = SloBreachedEvent(
            source_service="test",
            organization_id=uuid4(),
            payload={"slo_name": "api", "service_name": "gw", "status": "breaching", "value": 0.9},
        )
        await publisher(event)
        assert forwarded == [event]

    async def test_anomaly_detected_triggers_notification(self, manager) -> None:
        publisher, _ = await self._publisher(manager)
        event = AnomalyDetectedEvent(
            source_service="test",
            organization_id=uuid4(),
            payload={
                "service_name": "backend",
                "severity": "high",
                "method": "robust_zscore",
                "deviation": 5.2,
            },
        )
        await publisher(event)

    async def test_anomaly_detected_no_deviation(self, manager) -> None:
        publisher, _ = await self._publisher(manager)
        event = AnomalyDetectedEvent(
            source_service="test",
            organization_id=uuid4(),
            payload={
                "service_name": "backend",
                "severity": "low",
                "method": "threshold",
                "deviation": None,
            },
        )
        await publisher(event)

    async def test_capacity_forecast_warning_quality_notifies(self, manager) -> None:
        publisher, _ = await self._publisher(manager)
        event = CapacityForecastGeneratedEvent(
            source_service="test",
            organization_id=uuid4(),
            payload={
                "resource_kind": "disk",
                "quality": "unreliable",
                "days_until_exhaustion": None,
            },
        )
        await publisher(event)

    async def test_capacity_forecast_good_quality_no_notification(self, manager) -> None:
        publisher, _ = await self._publisher(manager)
        event = CapacityForecastGeneratedEvent(
            source_service="test",
            organization_id=uuid4(),
            payload={"resource_kind": "disk", "quality": "good", "days_until_exhaustion": 200.0},
        )
        await publisher(event)  # should not raise even though no notification fires

    async def test_root_cause_completed_triggers_notification(self, manager) -> None:
        publisher, _ = await self._publisher(manager)
        event = RootCauseCompletedEvent(
            source_service="test",
            organization_id=uuid4(),
            payload={
                "service_name": "checkout",
                "is_conclusive": True,
                "top_candidate_service": "payments",
            },
        )
        await publisher(event)

    async def test_unrelated_event_kind_no_notification(self, manager) -> None:
        publisher, forwarded = await self._publisher(manager)
        event = MetricCollectedEvent(source_service="test", organization_id=uuid4(), payload={})
        await publisher(event)
        assert forwarded == [event]
