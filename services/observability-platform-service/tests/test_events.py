"""Tests for app.events.domain_events -- registration and construction."""

from __future__ import annotations

from uuid import uuid4

from shared_core.events import default_registry

from app.events.domain_events import (
    AnomalyDetectedEvent,
    CapacityForecastGeneratedEvent,
    DashboardUpdatedEvent,
    LogIngestedEvent,
    MetricCollectedEvent,
    RootCauseCompletedEvent,
    SloBreachedEvent,
    TraceCompletedEvent,
)

_ALL_EVENTS = (
    MetricCollectedEvent,
    LogIngestedEvent,
    TraceCompletedEvent,
    AnomalyDetectedEvent,
    SloBreachedEvent,
    RootCauseCompletedEvent,
    CapacityForecastGeneratedEvent,
    DashboardUpdatedEvent,
)


class TestDomainEventRegistration:
    def test_all_eight_events_registered(self) -> None:
        for event_cls in _ALL_EVENTS:
            assert (
                default_registry.lookup(event_cls.event_name, event_cls.event_version) is event_cls
            )

    def test_each_event_constructs_with_generic_payload(self) -> None:
        for event_cls in _ALL_EVENTS:
            event = event_cls(
                source_service="observability-platform-service",
                organization_id=uuid4(),
                payload={"key": "value"},
            )
            assert event.event_name == event_cls.event_name
            assert event.payload == {"key": "value"}

    def test_event_versions_are_v1(self) -> None:
        for event_cls in _ALL_EVENTS:
            assert event_cls.event_version == "v1"

    def test_event_names_are_unique(self) -> None:
        names = [event_cls.event_name for event_cls in _ALL_EVENTS]
        assert len(names) == len(set(names))
