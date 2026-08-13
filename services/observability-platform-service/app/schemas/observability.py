"""Request and response schemas for the 13 docs/064 REST endpoints.

**No schema accepts an organization id.** It comes from the caller's
verified token and from nowhere else; a field here would let any caller
name any tenant, and every repository in this service scopes on the
value it is handed.

**Every optional numeric field stays optional on the way out.** A metric
value of ``None`` (no data), an SLI status of ``NO_DATA``, a forecast
with no interval -- each is a distinct engine finding, and a schema that
defaulted any of them to ``0.0`` would erase the distinction the pure
engines were built specifically to preserve.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AnomalyMethod,
    AnomalySeverity,
    AnomalyShape,
    CauseConfidence,
    EventKind,
    EventSeverity,
    ForecastQuality,
    LogLevel,
    NodeHealth,
    ReportFormat,
    ReportKind,
    ReportStatus,
    ResourceKind,
    SliKind,
    SpanStatus,
)

MAX_PAGE_SIZE = 500
MAX_NAME_LENGTH = 255


class _Base(BaseModel):
    """Shared configuration for every schema here.

    ``extra="forbid"`` on purpose: a client sending ``organization_id``
    in a body should get a clear rejection rather than have the field
    silently ignored while it believes it named another tenant.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- pagination, shared across list endpoints -----------------------------------


class PageInfo(_Base):
    """Cursor pagination info, matching ``app.search.query.SearchPage``."""

    next_cursor: str | None = None
    has_more: bool = False


# ---- GET /observability/metrics --------------------------------------------------


class MetricSampleResponse(_Base):
    occurred_at: datetime
    received_at: datetime
    value: float
    sample_count: int | None = None
    min_value: float | None = None
    max_value: float | None = None


class MetricSeriesResponse(_Base):
    id: UUID
    name: str
    metric_type: str
    unit: str | None
    service_name: str | None
    labels: dict[str, str]
    last_seen_at: datetime


class MetricsResponse(_Base):
    series: MetricSeriesResponse
    samples: list[MetricSampleResponse]
    page: PageInfo


# ---- GET /observability/logs -------------------------------------------------------


class LogEntryResponse(_Base):
    id: UUID
    occurred_at: datetime
    level: LogLevel
    message: str
    service_name: str | None
    trace_id: str | None
    parse_failed: bool


class LogsResponse(_Base):
    entries: list[LogEntryResponse]
    page: PageInfo


# ---- GET /observability/traces -----------------------------------------------------


class TraceSpanResponse(_Base):
    span_id: str
    parent_span_id: str | None
    name: str
    service_name: str
    status: SpanStatus
    started_at: datetime
    duration_ms: float
    self_time_ms: float | None


class TraceResponse(_Base):
    trace_id: str
    root_service_name: str | None
    started_at: datetime
    duration_ms: float | None
    is_complete: bool
    has_error: bool
    span_count: int
    spans: list[TraceSpanResponse]


# ---- GET /observability/events -----------------------------------------------------


class ObservabilityEventResponse(_Base):
    id: UUID
    event_kind: EventKind
    severity: EventSeverity
    title: str
    occurred_at: datetime
    ended_at: datetime | None
    service_name: str | None


class EventsResponse(_Base):
    events: list[ObservabilityEventResponse]
    page: PageInfo


# ---- GET /observability/topology ---------------------------------------------------


class TopologyEdgeResponse(_Base):
    caller_service: str
    callee_service: str
    call_count: int
    error_rate: float | None
    confidence: float
    is_stale: bool


class TopologyNodeResponse(_Base):
    service_name: str
    health: NodeHealth
    fan_in: int
    fan_out: int
    criticality: float
    in_cycle: bool


class TopologyResponse(_Base):
    environment: str
    nodes: list[TopologyNodeResponse]
    edges: list[TopologyEdgeResponse]


# ---- GET/POST /observability/slos --------------------------------------------------


class SloCreateRequest(_Base):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=2_000)
    service_name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    environment: str = Field(default="production", max_length=64)
    sli_kind: SliKind
    target: float = Field(gt=0.0, lt=1.0)
    latency_threshold_ms: float | None = Field(default=None, gt=0.0)
    window_days: int = Field(default=30, ge=1, le=395)
    is_rolling: bool = True
    owner: str | None = Field(default=None, max_length=128)


class SloResponse(_Base):
    id: UUID
    name: str
    description: str | None
    service_name: str
    environment: str
    sli_kind: SliKind
    target: float
    latency_threshold_ms: float | None
    window_days: int
    is_rolling: bool
    is_enabled: bool
    owner: str | None


class SlosResponse(_Base):
    slos: list[SloResponse]
    total: int


# ---- GET /observability/anomalies --------------------------------------------------


class AnomalyResponse(_Base):
    id: UUID
    metric_name: str | None
    service_name: str | None
    detected_at: datetime
    occurred_at: datetime
    method: AnomalyMethod
    shape: AnomalyShape
    severity: AnomalySeverity
    observed_value: float
    expected_value: float | None
    deviation: float | None
    rationale: str
    is_acknowledged: bool


class AnomaliesResponse(_Base):
    anomalies: list[AnomalyResponse]
    total: int


# ---- GET /observability/root-cause -------------------------------------------------


class RootCauseCandidateResponse(_Base):
    service: str
    rank: int
    tier: str
    distinguishable: bool
    correlation: float | None
    precedes_symptom: bool


class RootCauseResponse(_Base):
    id: UUID
    service_name: str
    incident_reference: str | None
    analysed_at: datetime
    confidence: CauseConfidence
    is_conclusive: bool
    summary: str | None
    candidates: list[RootCauseCandidateResponse]
    affected_service_count: int
    recommendations: list[str]


class RootCausesResponse(_Base):
    reports: list[RootCauseResponse]
    total: int


# ---- GET /observability/capacity ---------------------------------------------------


class CapacityForecastResponse(_Base):
    id: UUID
    service_name: str | None
    resource_kind: ResourceKind
    quality: ForecastQuality
    generated_at: datetime
    current_value: float | None
    forecast_value: float | None
    forecast_low: float | None
    forecast_high: float | None
    ceiling: float | None
    days_until_exhaustion: float | None
    exhaustion_at: datetime | None
    refusal_reason: str | None


class CapacityResponse(_Base):
    forecasts: list[CapacityForecastResponse]
    total: int


# ---- GET /observability/cost -------------------------------------------------------


class CostReportResponse(_Base):
    id: UUID
    period_start: datetime
    period_end: datetime
    dimension: str
    dimension_value: str | None
    currency: str
    total_cost: Decimal
    attributed_cost: Decimal
    unattributed_cost: Decimal
    allocated_shared_cost: Decimal


class CostResponse(_Base):
    reports: list[CostReportResponse]
    total: int


# ---- GET /observability/statistics -------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    metrics_ingested: int
    logs_ingested: int
    spans_ingested: int
    events_ingested: int
    rejected_count: int
    active_series_count: int
    error_log_count: int
    anomalies_detected: int
    slos_breaching: int


class StatisticsResponse(_Base):
    windows: list[StatisticWindowResponse]
    total: int


# ---- GET /observability/reports ----------------------------------------------------


class ReportResponse(_Base):
    id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: ReportStatus
    period_start: datetime | None
    period_end: datetime | None
    generated_at: datetime | None
    row_count: int | None


class ReportsResponse(_Base):
    reports: list[ReportResponse]
    total: int


__all__ = [
    "MAX_NAME_LENGTH",
    "MAX_PAGE_SIZE",
    "AnomaliesResponse",
    "AnomalyResponse",
    "CapacityForecastResponse",
    "CapacityResponse",
    "CostReportResponse",
    "CostResponse",
    "EventsResponse",
    "LogEntryResponse",
    "LogsResponse",
    "MetricSampleResponse",
    "MetricSeriesResponse",
    "MetricsResponse",
    "ObservabilityEventResponse",
    "PageInfo",
    "ReportResponse",
    "ReportsResponse",
    "RootCauseCandidateResponse",
    "RootCauseResponse",
    "RootCausesResponse",
    "SloCreateRequest",
    "SloResponse",
    "SlosResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "TopologyEdgeResponse",
    "TopologyNodeResponse",
    "TopologyResponse",
    "TraceResponse",
    "TraceSpanResponse",
]
