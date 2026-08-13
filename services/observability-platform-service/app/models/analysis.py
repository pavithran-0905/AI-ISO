"""The derived tables: ``service_dependencies``, ``service_topology``,
``slos``, ``slis``, ``anomaly_detections``, ``root_cause_reports``,
``capacity_forecasts`` and ``cost_reports``.

Everything here is a *conclusion* rather than an observation, and every
row carries the evidence that produced it. A conclusion whose basis was
not stored cannot be checked, cannot be explained to the person it wakes
up, and cannot be recomputed when the method improves.

**Every derived number that could not be computed is nullable**, and the
distinction is load-bearing: an SLI over a window with no traffic, a
forecast with too little history, and a root cause where the evidence did
not separate two candidates are each recorded as such rather than as a
zero, a flat line, or a confident pick.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    AnomalyMethod,
    AnomalySeverity,
    AnomalyShape,
    CauseConfidence,
    CostCategory,
    ForecastQuality,
    NodeHealth,
    ResourceKind,
    SliKind,
    SliStatus,
)


class ServiceDependency(BaseModel):
    """``service_dependencies`` -- one directed edge, derived from traces.

    An edge is evidence, not configuration. ``call_count`` is what
    separates a dependency exercised ten thousand times from one seen once
    in a retry path, and ``last_observed_at`` is what lets a removed
    dependency fade rather than being deleted -- deleting it would erase
    the history that explains last month's incident.
    """

    __tablename__ = "service_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "caller_service",
            "callee_service",
            "environment",
            name="uq_obs_dependency_edge",
        ),
        Index("ix_obs_dep_caller", "caller_service"),
        Index("ix_obs_dep_callee", "callee_service"),
        Index("ix_obs_dep_last_observed", "last_observed_at"),
    )

    caller_service: Mapped[str] = mapped_column(String(255), index=True)
    callee_service: Mapped[str] = mapped_column(String(255), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")
    operation: Mapped[str | None] = mapped_column(String(255), default=None)

    call_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    mean_latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    error_rate: Mapped[float | None] = mapped_column(Float, default=None)
    """``None`` where no calls were observed in the window. Zero would say
    the dependency is healthy when nothing exercised it."""

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    """How much to trust that this edge is real, from how often and how
    recently it was seen. An edge inferred from a single orphaned span is
    not the same claim as one from a million matched pairs."""
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class ServiceTopologyNode(BaseModel):
    """``service_topology`` -- one node, with its position in the graph.

    Fan-in and fan-out are stored because they are expensive to recompute
    per query and cheap to maintain per ingest. ``criticality`` is derived
    from them plus observed traffic, and its inputs are stored beside it so
    a surprising ranking can be argued with.
    """

    __tablename__ = "service_topology"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "service_name", "environment", name="uq_obs_topology_node"
        ),
        Index("ix_obs_topology_health", "health"),
        Index("ix_obs_topology_criticality", "criticality"),
    )

    service_name: Mapped[str] = mapped_column(String(255), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)
    source_kind: Mapped[str | None] = mapped_column(String(24), default=None)

    health: Mapped[NodeHealth] = mapped_column(String(16), default=NodeHealth.UNKNOWN, index=True)
    """``UNKNOWN`` for a node nothing has reported on, which is not the
    same as healthy and is frequently worse."""
    health_reason: Mapped[str | None] = mapped_column(String(512), default=None)

    fan_in: Mapped[int] = mapped_column(Integer, default=0)
    fan_out: Mapped[int] = mapped_column(Integer, default=0)
    depth_from_edge: Mapped[int | None] = mapped_column(Integer, default=None)
    criticality: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    criticality_inputs: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    """The components of the criticality score. A ranking nobody can take
    apart is a ranking nobody will act against."""

    request_rate: Mapped[float | None] = mapped_column(Float, default=None)
    error_rate: Mapped[float | None] = mapped_column(Float, default=None)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, default=None)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    in_cycle: Mapped[bool] = mapped_column(Boolean, default=False)
    """Real dependency graphs contain cycles. Recorded so a traversal can
    report that it stopped at one rather than appearing to have found a
    leaf."""
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class Slo(BaseModel):
    """``slos`` -- one service level objective.

    The objective, the window, and the burn-rate thresholds are all
    configuration; everything measured lives in :class:`Sli`. Separating
    them is what lets the objective be corrected without rewriting the
    history that was measured against the old one.
    """

    __tablename__ = "slos"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "environment", name="uq_obs_slo_name"),
        Index("ix_obs_slo_service", "service_name"),
        Index("ix_obs_slo_enabled", "is_enabled"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    service_name: Mapped[str] = mapped_column(String(255), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")

    sli_kind: Mapped[SliKind] = mapped_column(String(16))
    target: Mapped[float] = mapped_column(Float)
    """The objective as a fraction, e.g. 0.999. Stored as a fraction
    rather than a percentage so no caller has to guess which it is."""
    unit: Mapped[str | None] = mapped_column(String(32), default=None)
    latency_threshold_ms: Mapped[float | None] = mapped_column(Float, default=None)
    """For latency SLIs: the boundary that makes a request "good". A
    latency SLO without one is not an objective, it is an average."""
    percentile: Mapped[float | None] = mapped_column(Float, default=None)

    window_days: Mapped[int] = mapped_column(Integer, default=30)
    is_rolling: Mapped[bool] = mapped_column(Boolean, default=True)
    """Rolling window versus calendar period. They disagree by design at
    every month boundary, and a report that does not say which it used is
    not reproducible."""

    fast_burn_hours: Mapped[float] = mapped_column(Float, default=1.0)
    fast_burn_threshold: Mapped[float] = mapped_column(Float, default=14.4)
    slow_burn_hours: Mapped[float] = mapped_column(Float, default=6.0)
    slow_burn_threshold: Mapped[float] = mapped_column(Float, default=6.0)
    """Multi-window burn rate: both windows must exceed their threshold
    before this pages. A short window alone fires on every blip; a long
    window alone takes hours to notice a total outage."""

    query: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    owner: Mapped[str | None] = mapped_column(String(128), default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class Sli(BaseModel):
    """``slis`` -- one measurement of one SLO over one window.

    ``good_count`` and ``total_count`` are stored beside the computed
    ratio, because the ratio alone cannot be re-aggregated: the
    availability of two windows is not the mean of their availabilities
    unless both had identical traffic. Keeping the counts is what makes a
    30-day figure computable from 30 daily rows.
    """

    __tablename__ = "slis"
    __table_args__ = (
        UniqueConstraint("organization_id", "slo_id", "window_start", name="uq_obs_sli_window"),
        Index("ix_obs_sli_slo_time", "slo_id", "window_start"),
        Index("ix_obs_sli_status", "status"),
    )

    slo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slos.id", ondelete="CASCADE"), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    good_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[float | None] = mapped_column(Float, default=None)
    """The measured SLI as a fraction, or ``None`` when ``total_count`` was
    zero. A window with no traffic has an undefined availability, not a
    zero one -- and reporting zero pages somebody because a batch job was
    idle overnight."""

    status: Mapped[SliStatus] = mapped_column(String(16), default=SliStatus.NO_DATA, index=True)
    error_budget_total: Mapped[float | None] = mapped_column(Float, default=None)
    error_budget_consumed: Mapped[float | None] = mapped_column(Float, default=None)
    error_budget_remaining: Mapped[float | None] = mapped_column(Float, default=None)
    """May be negative, deliberately. Clamping an overspent budget to zero
    hides how far past it a service is, which is exactly the number that
    decides whether to freeze releases."""

    fast_burn_rate: Mapped[float | None] = mapped_column(Float, default=None)
    slow_burn_rate: Mapped[float | None] = mapped_column(Float, default=None)
    is_burning: Mapped[bool] = mapped_column(Boolean, default=False)
    projected_exhaustion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    """``None`` when the budget is not being consumed. A far-future date
    would be an invented prediction from a flat line."""

    percentile_value: Mapped[float | None] = mapped_column(Float, default=None)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class AnomalyDetection(BaseModel):
    """``anomaly_detections`` -- one detection, with why.

    ``expected_value`` and ``observed_value`` are stored beside the score
    because "6.2 deviations above expectation" is an answer an operator
    can check and "anomaly detected" is not.
    """

    __tablename__ = "anomaly_detections"
    __table_args__ = (
        Index("ix_obs_anomaly_time", "detected_at"),
        Index("ix_obs_anomaly_service", "service_name"),
        Index("ix_obs_anomaly_severity", "severity"),
        Index("ix_obs_anomaly_series", "metric_series_id"),
    )

    metric_series_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("metric_series.id", ondelete="CASCADE"), default=None, index=True
    )
    metric_name: Mapped[str | None] = mapped_column(String(255), default=None)
    service_name: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    method: Mapped[AnomalyMethod] = mapped_column(String(24))
    shape: Mapped[AnomalyShape] = mapped_column(String(24))
    severity: Mapped[AnomalySeverity] = mapped_column(
        String(16), default=AnomalySeverity.LOW, index=True
    )

    observed_value: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float, default=None)
    expected_low: Mapped[float | None] = mapped_column(Float, default=None)
    expected_high: Mapped[float | None] = mapped_column(Float, default=None)
    deviation: Mapped[float | None] = mapped_column(Float, default=None)
    """How far outside expectation, in robust deviations. ``None`` when the
    method does not produce one -- a threshold breach is a fact about a
    configured line, not a statistical distance."""

    baseline_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    """How much history the expectation was built from. A detection from
    six points and one from six thousand are different claims, and only
    this tells them apart."""
    rationale: Mapped[str] = mapped_column(String(1_024))
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class RootCauseReport(BaseModel):
    """``root_cause_reports`` -- ranked candidates for one incident.

    Candidates are a ranked *list* with per-candidate evidence, never a
    single answer. This engine establishes correlation and temporal
    precedence; it does not establish cause, and presenting one candidate
    as the cause sends people to fix the wrong thing.
    """

    __tablename__ = "root_cause_reports"
    __table_args__ = (
        Index("ix_obs_rca_time", "analysed_at"),
        Index("ix_obs_rca_service", "service_name"),
        Index("ix_obs_rca_confidence", "confidence"),
    )

    service_name: Mapped[str] = mapped_column(String(255), index=True)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)
    incident_reference: Mapped[str | None] = mapped_column(String(255), default=None, index=True)

    analysed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    incident_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    incident_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    confidence: Mapped[CauseConfidence] = mapped_column(
        String(24), default=CauseConfidence.INDISTINGUISHABLE, index=True
    )
    """Coarse bands, never a percentage. A percentage invites the reader to
    treat a correlation as a measured probability of causation."""

    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """Ranked, each with its own evidence and score. Order is the output."""
    timeline: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    blast_radius: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_service_count: Mapped[int] = mapped_column(Integer, default=0)
    recommendations: Mapped[list[str]] = mapped_column(JSON, default=list)

    signals_considered: Mapped[int] = mapped_column(Integer, default=0)
    is_conclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    """False when the evidence did not separate the top candidates. A
    confident wrong answer is worse than "these three are
    indistinguishable"."""
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class CapacityForecast(BaseModel):
    """``capacity_forecasts`` -- one resource projected forward.

    The interval is not optional. A point forecast with no interval is the
    commonest way capacity planning misleads: it reads as a prediction when
    it is the centre of a distribution whose width is the actual finding.
    """

    __tablename__ = "capacity_forecasts"
    __table_args__ = (
        Index("ix_obs_forecast_time", "generated_at"),
        Index("ix_obs_forecast_service", "service_name"),
        Index("ix_obs_forecast_resource", "resource_kind"),
        Index("ix_obs_forecast_quality", "quality"),
    )

    service_name: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)
    resource_kind: Mapped[ResourceKind] = mapped_column(String(16), index=True)
    metric_name: Mapped[str | None] = mapped_column(String(255), default=None)
    unit: Mapped[str | None] = mapped_column(String(32), default=None)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    history_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    history_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    history_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30)

    quality: Mapped[ForecastQuality] = mapped_column(
        String(16), default=ForecastQuality.INSUFFICIENT, index=True
    )
    r_squared: Mapped[float | None] = mapped_column(Float, default=None)
    slope_per_day: Mapped[float | None] = mapped_column(Float, default=None)
    intercept: Mapped[float | None] = mapped_column(Float, default=None)
    residual_std: Mapped[float | None] = mapped_column(Float, default=None)

    current_value: Mapped[float | None] = mapped_column(Float, default=None)
    forecast_value: Mapped[float | None] = mapped_column(Float, default=None)
    forecast_low: Mapped[float | None] = mapped_column(Float, default=None)
    forecast_high: Mapped[float | None] = mapped_column(Float, default=None)
    """The prediction interval, not a confidence interval on the mean. The
    two differ by a factor that grows with the horizon, and the wider one
    is the one capacity decisions need."""

    ceiling: Mapped[float | None] = mapped_column(Float, default=None)
    days_until_exhaustion: Mapped[float | None] = mapped_column(Float, default=None)
    """``None`` when the trend is flat or falling -- such a resource never
    exhausts, and a very large number would read as a date."""
    exhaustion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    forecast_basis: Mapped[str] = mapped_column(String(32), default="peak")
    """Peak rather than mean by default: capacity is sized for the busiest
    moment, and a mean-based forecast under-provisions by exactly the
    amount that matters."""
    refusal_reason: Mapped[str | None] = mapped_column(String(512), default=None)
    """Why no forecast was produced, when none was. A refusal a caller
    cannot explain is one they will work around."""
    points: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class CostReport(BaseModel):
    """``cost_reports`` -- spend for one period, attributed.

    Money is ``Numeric``, never float. A float total over a hundred
    thousand line items accumulates error that shows up as a few pence
    nobody can account for, and finance will not accept "floating point"
    as the explanation.
    """

    __tablename__ = "cost_reports"
    __table_args__ = (
        Index("ix_obs_cost_period", "period_start"),
        Index("ix_obs_cost_dimension", "dimension", "dimension_value"),
        Index("ix_obs_cost_category", "category"),
    )

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    dimension: Mapped[str] = mapped_column(String(24), index=True)
    dimension_value: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    category: Mapped[CostCategory | None] = mapped_column(String(16), default=None, index=True)

    currency: Mapped[str] = mapped_column(String(3), default="USD")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    attributed_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    unattributed_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    """Surfaced rather than dropped or silently spread. If a third of spend
    cannot be attributed, reporting only the attributed two thirds as "the
    total" understates every project's real share."""
    allocated_shared_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    allocation_basis: Mapped[str | None] = mapped_column(String(64), default=None)

    by_category: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    by_service: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    """Decimal amounts serialised as strings. Round-tripping money through
    JSON floats reintroduces exactly the error ``Numeric`` was chosen to
    avoid."""

    unit_count: Mapped[int | None] = mapped_column(Integer, default=None)
    cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), default=None)
    """``None`` when the denominator was zero. Cost per request over a
    period with no requests is undefined, not infinite and not zero."""
    unit_label: Mapped[str | None] = mapped_column(String(64), default=None)

    rate_card_version: Mapped[str | None] = mapped_column(String(64), default=None)
    """Which prices produced these numbers. Without it a report cannot be
    reproduced after a price change, and two reports cannot be compared."""
    previous_period_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=None)
    change_ratio: Mapped[float | None] = mapped_column(Float, default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = [
    "AnomalyDetection",
    "CapacityForecast",
    "CostReport",
    "RootCauseReport",
    "ServiceDependency",
    "ServiceTopologyNode",
    "Sli",
    "Slo",
]
