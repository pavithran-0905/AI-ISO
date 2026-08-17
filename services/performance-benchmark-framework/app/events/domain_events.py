"""The domain events this service publishes (docs/078 "EVENTS",
integrating Prompt 020).

All eight spec-named events. **Every event is registered with the
shared registry at import time.** ``EventManager.publish`` validates
against :data:`shared_core.events.registry.default_registry` and
refuses anything unregistered as ``AIIOS-EVENT-0002``.

**Fields live in ``payload``**, per :class:`~shared_core.events.base.BaseEvent`
-- not as typed attributes on each subclass, matching the convention
every other AI-IOS service follows.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class BenchmarkStartedEvent(DomainEvent):
    """A benchmark run began.

    Expected payload: ``benchmark_run_id``, ``benchmark_suite_id``.
    """

    event_name: ClassVar[str] = "BenchmarkStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class BenchmarkCompletedEvent(DomainEvent):
    """A benchmark run reached a terminal state, regardless of whether
    it succeeded or failed.

    Expected payload: ``benchmark_run_id``, ``status``.
    """

    event_name: ClassVar[str] = "BenchmarkCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RegressionDetectedEvent(DomainEvent):
    """A metric regressed against its own baseline beyond the
    configured warning threshold.

    Expected payload: ``performance_regression_id``, ``metric_name``, ``severity``.
    """

    event_name: ClassVar[str] = "RegressionDetected"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CapacityThresholdReachedEvent(DomainEvent):
    """A capacity forecast's own projected value reached its threshold.

    Expected payload: ``capacity_forecast_id``, ``capacity_model_id``.
    """

    event_name: ClassVar[str] = "CapacityThresholdReached"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OptimizationGeneratedEvent(DomainEvent):
    """A new optimization recommendation was generated.

    Expected payload: ``optimization_recommendation_id``, ``category``.
    """

    event_name: ClassVar[str] = "OptimizationGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SLOViolatedEvent(DomainEvent):
    """A named SLO's own latest evaluation was non-compliant.

    Expected payload: ``slo_name``, ``sli_type``.
    """

    event_name: ClassVar[str] = "SLOViolated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PerformanceImprovedEvent(DomainEvent):
    """A metric improved on its own baseline beyond the configured
    improvement threshold.

    Expected payload: ``metric_name``, ``benchmark_suite_id``.
    """

    event_name: ClassVar[str] = "PerformanceImproved"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class BaselineUpdatedEvent(DomainEvent):
    """A metric's own baseline was set or replaced.

    Expected payload: ``benchmark_baseline_id``, ``metric_name``.
    """

    event_name: ClassVar[str] = "BaselineUpdated"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "BaselineUpdatedEvent",
    "BenchmarkCompletedEvent",
    "BenchmarkStartedEvent",
    "CapacityThresholdReachedEvent",
    "OptimizationGeneratedEvent",
    "PerformanceImprovedEvent",
    "RegressionDetectedEvent",
    "SLOViolatedEvent",
]
