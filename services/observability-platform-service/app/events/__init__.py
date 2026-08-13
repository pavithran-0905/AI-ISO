"""Domain events published by this service.

The event module is imported here for its side effect: each class
registers with the shared registry at import time, and an event class
that was never imported is one ``EventManager.publish`` refuses with
``AIIOS-EVENT-0002`` at the moment a real detection or forecast tries to
use it.
"""

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

__all__ = [
    "AnomalyDetectedEvent",
    "CapacityForecastGeneratedEvent",
    "DashboardUpdatedEvent",
    "LogIngestedEvent",
    "MetricCollectedEvent",
    "RootCauseCompletedEvent",
    "SloBreachedEvent",
    "TraceCompletedEvent",
]
