"""The raw signal tables: ``metrics``, ``metric_series``, ``log_entries``,
``trace_spans``, ``trace_sessions``, ``events`` and ``profiles``.

**A series is separate from its samples.** A metric's identity -- its
name, type, unit and label set -- is stable across millions of samples,
and repeating it on every row costs more storage than the samples
themselves and makes "what series exist" a full scan. The series row also
carries the *type*, which is what lets the aggregator refuse to average a
counter.

**Every timestamped row records when the event happened and when it was
received.** Those differ, sometimes by hours: an edge node reconnecting
after an outage backfills a day of samples, and a query over "the last
hour" that used the received time would show them all as happening now.
Late arrival is a fact worth keeping, not a discrepancy to paper over.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    EventKind,
    EventSeverity,
    LogFormat,
    LogLevel,
    MetricKind,
    MetricType,
    ProfileKind,
    RetentionTier,
    SourceKind,
    SpanKind,
    SpanStatus,
)


class MetricSeries(BaseModel):
    """``metric_series`` -- the identity of a metric, once.

    Labels live in a JSON column *and* in a ``label_fingerprint``. The
    fingerprint is what the unique constraint is on, because two label
    sets that differ only in key order are the same series and a
    constraint on the JSON itself would let both exist -- silently
    splitting one series in two and halving every rate computed from it.
    """

    __tablename__ = "metric_series"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", "label_fingerprint", name="uq_obs_series_identity"
        ),
        Index("ix_obs_series_name", "name"),
        Index("ix_obs_series_service", "service_name"),
        Index("ix_obs_series_last_seen", "last_seen_at"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    metric_type: Mapped[MetricType] = mapped_column(String(16))
    """Stored, never inferred. Averaging a counter is a fact about how long
    a process has been running rather than about the system, and the
    aggregator needs this to refuse."""
    metric_kind: Mapped[MetricKind] = mapped_column(String(24), default=MetricKind.CUSTOM)
    unit: Mapped[str | None] = mapped_column(String(32), default=None)
    """The unit the samples are in. Without it a chart cannot label its own
    axis, and two series in different units get summed into nonsense."""
    description: Mapped[str | None] = mapped_column(String(512), default=None)

    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    label_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    """A stable hash of the sorted label pairs. See the class docstring."""

    service_name: Mapped[str | None] = mapped_column(String(255), default=None)
    source_kind: Mapped[SourceKind] = mapped_column(
        String(24), default=SourceKind.CUSTOM_APPLICATION
    )
    environment: Mapped[str | None] = mapped_column(String(64), default=None, index=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    """What makes a stale series visible. A series nothing has written to
    for a week is usually a removed instrumentation point, and it should
    stop appearing in pickers rather than being silently deleted."""
    sample_count: Mapped[int] = mapped_column(BigInteger, default=0)
    retention_tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.RAW)


class Metric(BaseModel):
    """``metrics`` -- one sample of one series.

    Histogram samples carry their bucket counts rather than only their
    computed percentiles, because percentiles cannot be re-aggregated: the
    p99 of two windows is not the mean of their p99s, and only the buckets
    let a later query compute the p99 of their union.
    """

    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_obs_metric_series_time", "metric_series_id", "occurred_at"),
        Index("ix_obs_metric_occurred", "occurred_at"),
    )

    metric_series_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metric_series.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Kept beside ``occurred_at`` so late arrival is measurable. An edge
    node backfilling a day of samples after an outage is a normal event,
    and a query that conflated the two would report all of it as now."""

    value: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int | None] = mapped_column(Integer, default=None)
    """How many observations this row summarises, for pre-aggregated
    samples. ``None`` means one raw observation. A weighted mean needs
    this; an unweighted one over pre-aggregated rows is wrong in
    proportion to how uneven the batches were."""
    sum_value: Mapped[float | None] = mapped_column(Float, default=None)
    min_value: Mapped[float | None] = mapped_column(Float, default=None)
    max_value: Mapped[float | None] = mapped_column(Float, default=None)
    buckets: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    """Histogram bucket upper bounds to cumulative counts. See the class
    docstring for why the computed percentiles alone are not enough."""

    retention_tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.RAW)
    """Downsampling is lossy and irreversible, so a chart drawn from
    coarse rows must not be presented as if it had raw resolution."""


class LogEntry(BaseModel):
    """``log_entries`` -- one log line, parsed as far as it could be.

    A line that could not be parsed is stored with its raw text and
    ``parse_failed`` set, never dropped. A logging pipeline that silently
    discards what it cannot read is one that hides the exact lines a new
    failure mode produces -- which are the ones worth reading.
    """

    __tablename__ = "log_entries"
    __table_args__ = (
        Index("ix_obs_log_time", "occurred_at"),
        Index("ix_obs_log_service_time", "service_name", "occurred_at"),
        Index("ix_obs_log_level", "level"),
        Index("ix_obs_log_trace", "trace_id"),
    )

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    level: Mapped[LogLevel] = mapped_column(String(16), default=LogLevel.INFO, index=True)
    message: Mapped[str] = mapped_column(Text)
    raw: Mapped[str | None] = mapped_column(Text, default=None)
    """The original line, kept when parsing changed anything. Without it a
    parser bug is unfalsifiable after the fact."""

    log_format: Mapped[LogFormat] = mapped_column(String(16), default=LogFormat.PLAIN)
    parse_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    parse_error: Mapped[str | None] = mapped_column(String(512), default=None)

    service_name: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    source_kind: Mapped[SourceKind] = mapped_column(
        String(24), default=SourceKind.CUSTOM_APPLICATION
    )
    environment: Mapped[str | None] = mapped_column(String(64), default=None)
    host: Mapped[str | None] = mapped_column(String(255), default=None)

    trace_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    span_id: Mapped[str | None] = mapped_column(String(32), default=None)
    """What makes a log line correlatable with a trace. A platform that
    stores logs and traces separately with no join key can show you both
    and never the one alongside the other."""

    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    retention_tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.RAW)


class TraceSession(BaseModel):
    """``trace_sessions`` -- one whole trace, summarised.

    Derived from its spans rather than reported by a client, because no
    single service sees the whole trace. ``is_complete`` records whether
    the root span was ever received: a trace missing its root has an
    unknown total duration, and treating the earliest span seen as the
    start understates it by however much was sampled out.
    """

    __tablename__ = "trace_sessions"
    __table_args__ = (
        UniqueConstraint("organization_id", "trace_id", name="uq_obs_trace_session"),
        Index("ix_obs_trace_started", "started_at"),
        Index("ix_obs_trace_root_service", "root_service_name"),
        Index("ix_obs_trace_error", "has_error"),
    )

    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    root_span_id: Mapped[str | None] = mapped_column(String(32), default=None)
    root_service_name: Mapped[str | None] = mapped_column(String(255), default=None)
    root_operation: Mapped[str | None] = mapped_column(String(255), default=None)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    """``None`` until the root span arrives. A duration computed from an
    incomplete trace is a lower bound presented as a measurement."""

    span_count: Mapped[int] = mapped_column(Integer, default=0)
    error_span_count: Mapped[int] = mapped_column(Integer, default=0)
    service_count: Mapped[int] = mapped_column(Integer, default=0)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)

    has_error: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    orphan_span_count: Mapped[int] = mapped_column(Integer, default=0)
    """Spans whose parent was never received, usually because it was
    sampled out. Recorded rather than reparented, since guessing a parent
    invents a dependency edge that no request ever made."""

    sampled: Mapped[bool] = mapped_column(Boolean, default=True)
    services: Mapped[list[str]] = mapped_column(JSON, default=list)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class TraceSpan(BaseModel):
    """``trace_spans`` -- one span.

    ``span_kind`` is what makes a dependency edge directional: a CLIENT
    span in one service whose child is a SERVER span in another is
    evidence that the first depends on the second, and not the reverse.
    """

    __tablename__ = "trace_spans"
    __table_args__ = (
        UniqueConstraint("organization_id", "trace_id", "span_id", name="uq_obs_span_identity"),
        Index("ix_obs_span_trace", "trace_id"),
        Index("ix_obs_span_parent", "parent_span_id"),
        Index("ix_obs_span_service_time", "service_name", "started_at"),
        Index("ix_obs_span_status", "status"),
    )

    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    span_id: Mapped[str] = mapped_column(String(32))
    parent_span_id: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    trace_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trace_sessions.id", ondelete="CASCADE"), default=None
    )

    name: Mapped[str] = mapped_column(String(255))
    span_kind: Mapped[SpanKind] = mapped_column(String(16), default=SpanKind.INTERNAL)
    status: Mapped[SpanStatus] = mapped_column(String(16), default=SpanStatus.UNSET, index=True)
    """``UNSET`` is OpenTelemetry's default and is distinct from ``OK``.
    Counting unset spans as successes inflates every success rate computed
    from traces."""
    status_message: Mapped[str | None] = mapped_column(String(512), default=None)

    service_name: Mapped[str] = mapped_column(String(255), index=True)
    source_kind: Mapped[SourceKind] = mapped_column(String(24), default=SourceKind.MICROSERVICE)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float] = mapped_column(Float)
    self_time_ms: Mapped[float | None] = mapped_column(Float, default=None)
    """Duration minus time spent in children. What identifies where time
    actually went: a slow span whose children account for all of it is not
    itself slow, it is waiting."""

    depth: Mapped[int] = mapped_column(Integer, default=0)
    is_orphan: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    events: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    retention_tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.RAW)


class ObservabilityEvent(BaseModel):
    """``events`` -- something that happened, as distinct from something
    that was measured.

    Named ``ObservabilityEvent`` rather than ``Event`` because this
    service also publishes *domain* events through shared-core, and one
    ``Event`` in two senses in one codebase is a bug waiting for a tired
    reader.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_obs_event_time", "occurred_at"),
        Index("ix_obs_event_kind", "event_kind"),
        Index("ix_obs_event_severity", "severity"),
        Index("ix_obs_event_service", "service_name"),
    )

    event_kind: Mapped[EventKind] = mapped_column(String(24), index=True)
    severity: Mapped[EventSeverity] = mapped_column(
        String(16), default=EventSeverity.INFO, index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    """Set for events with duration -- a deployment, a maintenance window.
    An instantaneous event leaves it null rather than repeating
    ``occurred_at``, so "was this still in effect at time T" has one
    answer rather than two."""

    service_name: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    source_kind: Mapped[SourceKind] = mapped_column(String(24), default=SourceKind.PLATFORM_SERVICE)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)
    host: Mapped[str | None] = mapped_column(String(255), default=None)

    trace_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)

    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    retention_tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.RAW)


class Profile(BaseModel):
    """``profiles`` -- one profiling sample set.

    Stored as flattened stack frames with self and cumulative counts
    rather than as a rendered flame graph, because the rendering is a view
    and the counts are the data. A stored image cannot be re-aggregated,
    filtered, or diffed against yesterday's.
    """

    __tablename__ = "profiles"
    __table_args__ = (
        Index("ix_obs_profile_time", "captured_at"),
        Index("ix_obs_profile_service", "service_name"),
        Index("ix_obs_profile_kind", "profile_kind"),
    )

    profile_kind: Mapped[ProfileKind] = mapped_column(String(16), index=True)
    service_name: Mapped[str] = mapped_column(String(255), index=True)
    source_kind: Mapped[SourceKind] = mapped_column(String(24), default=SourceKind.MICROSERVICE)
    environment: Mapped[str | None] = mapped_column(String(64), default=None)
    host: Mapped[str | None] = mapped_column(String(255), default=None)

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    sample_period_ms: Mapped[float | None] = mapped_column(Float, default=None)
    """How often the profiler sampled. Without it, sample counts from two
    profilers at different rates cannot be compared, and a "hotter"
    function may simply have been watched more closely."""

    unit: Mapped[str | None] = mapped_column(String(32), default=None)
    total_value: Mapped[float] = mapped_column(Float, default=0.0)
    frames: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """Flattened frames: function, file, line, self value, cumulative
    value. See the class docstring for why not a rendered graph."""
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    retention_tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.RAW)


__all__ = [
    "LogEntry",
    "Metric",
    "MetricSeries",
    "ObservabilityEvent",
    "Profile",
    "TraceSession",
    "TraceSpan",
]
