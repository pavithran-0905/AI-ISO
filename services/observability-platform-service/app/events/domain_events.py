"""The domain events this service publishes (docs/064 "EVENTS",
integrating Prompt 020).

All eight the spec names. **Every event is registered with the shared
registry at import time.** ``EventManager.publish`` validates against
:data:`shared_core.events.registry.default_registry` and refuses
anything unregistered as ``AIIOS-EVENT-0002`` -- an error at the moment a
real detection or forecast tries to announce itself, not at review time,
which is exactly why the decorator lives here rather than being assumed.

**Fields live in ``payload``, per :class:`~shared_core.events.base.BaseEvent`**,
not as typed attributes on each subclass -- the base already carries a
generic ``payload: dict[str, Any]``, and every other event in this
platform is constructed the same way, so a consumer that knows one
service's event shape already knows the envelope for all of them.

**Payloads carry identifiers, counts, and classifications -- never raw
signal content.** A ``LogIngested`` event carrying log messages would put
customer log lines on the message bus, in every subscriber's queue, and
in any dead-letter store they land in. A consumer that needs the content
fetches it through the API, where access control applies.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class MetricCollectedEvent(DomainEvent):
    """A batch of metric samples was accepted.

    Expected payload: ``metric_series_id``, ``series_name``,
    ``accepted_count``.
    """

    event_name: ClassVar[str] = "MetricCollected"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class LogIngestedEvent(DomainEvent):
    """A batch of log lines was ingested.

    Expected payload: ``accepted_count``, ``parse_failed_count``.
    The two travel separately rather than folded into one number: a
    collector that starts emitting a format the parser does not
    recognise is a pipeline health signal an operator needs to see even
    while every line is still being accepted and stored.
    """

    event_name: ClassVar[str] = "LogIngested"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class TraceCompletedEvent(DomainEvent):
    """A trace session reached completeness -- its root span arrived.

    Expected payload: ``trace_id``, ``root_service_name``, ``span_count``,
    ``has_error``, ``duration_ms``.

    Published only when :class:`~app.models.signals.TraceSession.is_complete`
    transitions to ``True``, never on every span. A consumer subscribing
    to this event wants one notification per trace, not one per span in
    it.
    """

    event_name: ClassVar[str] = "TraceCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class AnomalyDetectedEvent(DomainEvent):
    """A new anomaly was detected and persisted.

    Expected payload: ``detection_id``, ``metric_series_id``,
    ``service_name``, ``severity``, ``method``, ``deviation``.

    Never published for a detection
    :meth:`~app.repositories.analysis.AnomalyDetectionRepository.find_existing`
    found already recorded -- an overlapping sweep re-observing the same
    instant must not re-announce it.
    """

    event_name: ClassVar[str] = "AnomalyDetected"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SloBreachedEvent(DomainEvent):
    """An SLO's status moved to ``BREACHING``, ``AT_RISK``, or ``EXHAUSTED``.

    Expected payload: ``slo_id``, ``sli_id``, ``status``, ``value``,
    ``error_budget_remaining``.

    Not published for ``HEALTHY`` or ``NO_DATA`` -- those are not
    breaches, and a consumer paging on this event does not want an
    all-clear treated as the same kind of notification as an incident.
    """

    event_name: ClassVar[str] = "SLOBreached"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RootCauseCompletedEvent(DomainEvent):
    """A root cause analysis finished, conclusive or not.

    Expected payload: ``report_id``, ``service_name``, ``is_conclusive``,
    ``top_candidate_service``.

    ``is_conclusive`` travels in the payload rather than being implied by
    publishing-or-not: an inconclusive analysis is still a finished one,
    and a consumer tracking incident response needs to know the analysis
    ran even when it could not name a single cause.
    """

    event_name: ClassVar[str] = "RootCauseCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CapacityForecastGeneratedEvent(DomainEvent):
    """A capacity forecast was produced -- or refused, with the reason.

    Expected payload: ``forecast_id``, ``resource_kind``, ``quality``,
    ``days_until_exhaustion``.

    ``quality`` is always set, including ``INSUFFICIENT``/``UNRELIABLE``
    for a refusal: :class:`~app.services.capacity.CapacityForecastService`
    persists exactly one row per run either way, and this event mirrors
    that discipline rather than only firing on a successful fit.
    """

    event_name: ClassVar[str] = "CapacityForecastGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DashboardUpdatedEvent(DomainEvent):
    """A dashboard's panels, layout, or variables changed.

    Expected payload: ``dashboard_id``, ``updated_by``.
    """

    event_name: ClassVar[str] = "DashboardUpdated"
    event_version: ClassVar[str] = "v1"


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
