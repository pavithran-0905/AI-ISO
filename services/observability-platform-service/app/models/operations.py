"""The operational tables: ``observability_statistics``,
``observability_reports``, ``observability_audit``, plus the saved queries
and dashboards the SEARCH and DASHBOARDS sections require.

The audit trail is append-only by convention and by absence: there is no
update path to it anywhere in this service, because a trail that can be
edited is a trail that proves nothing.
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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    AuditAction,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SignalKind,
)


class ObservabilityStatistic(BaseModel):
    """``observability_statistics`` -- one rolled-up window per organization.

    Rollup is idempotent per window: the worker updates the row for a
    window rather than inserting a second, because two rows for one window
    double-count every signal in it with no way to tell afterwards which
    is real.
    """

    __tablename__ = "observability_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "window_start", name="uq_obs_statistic_window"),
        Index("ix_obs_statistic_window", "window_start"),
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    metrics_ingested: Mapped[int] = mapped_column(BigInteger, default=0)
    logs_ingested: Mapped[int] = mapped_column(BigInteger, default=0)
    spans_ingested: Mapped[int] = mapped_column(BigInteger, default=0)
    events_ingested: Mapped[int] = mapped_column(BigInteger, default=0)
    profiles_ingested: Mapped[int] = mapped_column(BigInteger, default=0)
    rejected_count: Mapped[int] = mapped_column(BigInteger, default=0)
    """Signals refused at ingest. Reported beside the accepted counts,
    because an ingest pipeline that only publishes its throughput looks
    identical whether it is accepting everything or a tenth of it."""

    active_series_count: Mapped[int] = mapped_column(Integer, default=0)
    active_service_count: Mapped[int] = mapped_column(Integer, default=0)
    error_log_count: Mapped[int] = mapped_column(BigInteger, default=0)
    error_span_count: Mapped[int] = mapped_column(BigInteger, default=0)

    anomalies_detected: Mapped[int] = mapped_column(Integer, default=0)
    slos_breaching: Mapped[int] = mapped_column(Integer, default=0)
    slos_no_data: Mapped[int] = mapped_column(Integer, default=0)
    """Counted separately from breaching. An SLO with no data is not
    passing and not failing -- it is unmeasured, and rolling it into either
    column makes the compliance figure a fiction."""

    mean_ingest_lag_ms: Mapped[float | None] = mapped_column(Float, default=None)
    max_ingest_lag_ms: Mapped[float | None] = mapped_column(Float, default=None)
    """The gap between when a signal happened and when it arrived. The max
    matters more than the mean: one source an hour behind is invisible in
    an average over a million prompt ones."""

    storage_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    by_signal_kind: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    by_service: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    by_source_kind: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    top_error_services: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    noisiest_series: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """The series producing the most volume, which is the most actionable
    output here: it names exactly which instrumentation to turn down."""


class ObservabilityReport(BaseModel):
    """``observability_reports`` -- one generated report."""

    __tablename__ = "observability_reports"
    __table_args__ = (
        Index("ix_obs_report_kind", "kind"),
        Index("ix_obs_report_status", "status"),
    )

    kind: Mapped[ReportKind] = mapped_column(String(24), index=True)
    report_format: Mapped[ReportFormat] = mapped_column(String(16), default=ReportFormat.JSON)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[ReportStatus] = mapped_column(
        String(16), default=ReportStatus.PENDING, index=True
    )

    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    content: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)

    generated_by: Mapped[str | None] = mapped_column(String(128), default=None)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class ObservabilityAudit(BaseModel):
    """``observability_audit`` -- the immutable trail.

    Queries are audited as well as writes. In an observability platform the
    read path is the sensitive one: logs and traces carry whatever the
    instrumented services put in them, and who searched for what is
    exactly the question an incident review asks.
    """

    __tablename__ = "observability_audit"
    __table_args__ = (
        Index("ix_obs_audit_time", "occurred_at"),
        Index("ix_obs_audit_action", "action"),
        Index("ix_obs_audit_actor", "actor_id"),
    )

    action: Mapped[AuditAction] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    entity_reference: Mapped[str | None] = mapped_column(String(512), default=None)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    summary: Mapped[str | None] = mapped_column(String(512), default=None)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)

    signal_kind: Mapped[SignalKind | None] = mapped_column(String(16), default=None)
    record_count: Mapped[int | None] = mapped_column(BigInteger, default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class SavedQuery(BaseModel):
    """``saved_queries`` -- a named search, per the spec's SEARCH section.

    Not in the spec's table list and added because "Saved Queries" is in
    its SEARCH requirements: a saved query with nowhere to live is a
    feature that cannot be implemented.
    """

    __tablename__ = "saved_queries"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_obs_saved_query_name"),
        Index("ix_obs_saved_query_signal", "signal_kind"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    signal_kind: Mapped[SignalKind] = mapped_column(String(16), index=True)
    query: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped[str | None] = mapped_column(String(128), default=None)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    mean_duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class Dashboard(BaseModel):
    """``dashboards`` -- a saved arrangement of panels.

    Also not in the spec's table list, and added for the same reason: the
    DASHBOARDS section requires custom dashboards and sharing, and neither
    is possible without somewhere to keep them.
    """

    __tablename__ = "dashboards"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_obs_dashboard_slug"),
        Index("ix_obs_dashboard_shared", "is_shared"),
    )

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    panels: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    layout: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    variables: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped[str | None] = mapped_column(String(128), default=None)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class RetentionPolicy(BaseModel):
    """``retention_policies`` -- how long each signal kind is kept.

    Configuration rather than a constant, because retention is a
    compliance decision that differs per organization and per signal:
    audit logs frequently must be kept for years while debug logs must be
    discarded within days, and a single platform-wide constant cannot
    satisfy both.
    """

    __tablename__ = "retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "signal_kind", "environment", name="uq_obs_retention_scope"
        ),
    )

    signal_kind: Mapped[SignalKind] = mapped_column(String(16), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")

    raw_days: Mapped[int] = mapped_column(Integer, default=7)
    downsampled_days: Mapped[int] = mapped_column(Integer, default=30)
    coarse_days: Mapped[int] = mapped_column(Integer, default=395)
    """Just over thirteen months by default, so a year-on-year comparison
    has both endpoints. Exactly 365 leaves last year's same-week figure
    already deleted on the day you want it."""

    downsample_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_deleted_count: Mapped[int | None] = mapped_column(BigInteger, default=None)


__all__ = [
    "Dashboard",
    "ObservabilityAudit",
    "ObservabilityReport",
    "ObservabilityStatistic",
    "RetentionPolicy",
    "SavedQuery",
]
