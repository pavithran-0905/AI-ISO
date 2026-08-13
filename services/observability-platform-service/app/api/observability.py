"""The 13 docs/064 REST endpoints.

**Static segments are declared before any path parameter.** None of
these 13 routes actually take a path parameter (every lookup is by query
string), so the ordering trap that catches ``/documents/{id}`` does not
apply here -- noted because the next route added to this router should
keep it that way, or check this file's history for why it mattered
elsewhere in this platform.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see :func:`app.api.deps.get_organization_id`
for why that is not a convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CurrentUserId,
    OrganizationId,
    Repos,
    Search,
    require_administrator,
)
from app.models.analysis import Slo
from app.models.enums import (
    AnomalySeverity,
    EventKind,
    EventSeverity,
    LogLevel,
    ReportStatus,
    SignalKind,
)
from app.schemas.observability import (
    MAX_PAGE_SIZE,
    AnomaliesResponse,
    AnomalyResponse,
    CapacityForecastResponse,
    CapacityResponse,
    CostReportResponse,
    CostResponse,
    EventsResponse,
    LogEntryResponse,
    LogsResponse,
    MetricSampleResponse,
    MetricSeriesResponse,
    MetricsResponse,
    ObservabilityEventResponse,
    PageInfo,
    ReportResponse,
    ReportsResponse,
    RootCauseCandidateResponse,
    RootCauseResponse,
    RootCausesResponse,
    SloCreateRequest,
    SloResponse,
    SlosResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    TopologyEdgeResponse,
    TopologyNodeResponse,
    TopologyResponse,
    TraceResponse,
    TraceSpanResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.search.query import SearchFilter, SearchRequest, TimeRange

router = APIRouter(prefix="/observability", tags=["Observability"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


# ---- GET /observability/metrics ----------------------------------------------------


@router.get(
    "/metrics", response_model=SuccessResponse[MetricsResponse], summary="Query one metric series"
)
async def get_metrics(
    organization_id: OrganizationId,
    repos: Repos,
    series_id: UUID,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 200,
) -> SuccessResponse[MetricsResponse]:
    """Samples for one metric series in a bounded time window.

    Raises 404 when the series does not exist in the caller's
    organization -- never an empty sample list, which would be
    indistinguishable from "this series exists but had no traffic".
    """
    series = await repos.metric_series.require_in_org(organization_id, series_id)
    window_start, window_end = (start, end) if start and end else _default_window(1)
    rows = await repos.metrics.list_for_series(
        series_id, start=window_start, end=window_end, limit=limit
    )
    page_rows, has_more = (rows[:limit], len(rows) > limit)
    data = MetricsResponse(
        series=MetricSeriesResponse(
            id=series.id,
            name=series.name,
            metric_type=str(series.metric_type),
            unit=series.unit,
            service_name=series.service_name,
            labels=series.labels,
            last_seen_at=series.last_seen_at,
        ),
        samples=[
            MetricSampleResponse(
                occurred_at=row.occurred_at,
                received_at=row.received_at,
                value=row.value,
                sample_count=row.sample_count,
                min_value=row.min_value,
                max_value=row.max_value,
            )
            for row in page_rows
        ],
        page=PageInfo(has_more=has_more),
    )
    return SuccessResponse(message="Metrics retrieved.", data=data, meta=_meta())


# ---- GET /observability/logs -------------------------------------------------------


@router.get("/logs", response_model=SuccessResponse[LogsResponse], summary="Search logs")
async def get_logs(
    organization_id: OrganizationId,
    search: Search,
    start: datetime | None = None,
    end: datetime | None = None,
    service_name: str | None = None,
    level: LogLevel | None = None,
    trace_id: str | None = None,
    text: str | None = None,
    cursor: str | None = None,
    page_size: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
) -> SuccessResponse[LogsResponse]:
    """Bounded, cursor-paginated log search. See ``app.search.query``."""
    window_start, window_end = (start, end) if start and end else _default_window(1)
    filters = tuple(
        SearchFilter(field, value)
        for field, value in (
            ("service", service_name),
            ("level", level.value if level else None),
            ("trace_id", trace_id),
        )
        if value is not None
    )
    request = SearchRequest(
        signal_kind=SignalKind.LOG,
        time_range=TimeRange(window_start, window_end),
        filters=filters,
        text=text,
        page_size=page_size,
        cursor=cursor,
    )
    result = await search.search(organization_id, request, now=datetime.now(UTC))
    validation, rows = result if isinstance(result, tuple) else (result, [])
    if not validation.is_valid:
        raise ValidationError(validation.detail or "Invalid search request.")

    page = search.paginate(validation, rows)
    data = LogsResponse(
        entries=[
            LogEntryResponse(
                id=row.record_id,
                occurred_at=row.occurred_at,
                level=LogLevel(str(row.payload["level"])),
                message=str(row.payload["message"]),
                service_name=row.payload.get("service_name"),
                trace_id=trace_id,
                parse_failed=False,
            )
            for row in page.rows
        ],
        page=PageInfo(next_cursor=page.next_cursor, has_more=page.has_more),
    )
    return SuccessResponse(message="Logs retrieved.", data=data, meta=_meta())


# ---- GET /observability/traces -----------------------------------------------------


@router.get("/traces", response_model=SuccessResponse[TraceResponse], summary="Retrieve one trace")
async def get_trace(
    organization_id: OrganizationId, repos: Repos, trace_id: str
) -> SuccessResponse[TraceResponse]:
    """One trace's session summary plus every span, in start order.

    Raises 404 for an unknown trace id -- distinct from a trace that
    exists but has zero spans, which cannot happen: a session is only
    ever created alongside its first span.
    """
    session = await repos.trace_sessions.find_by_trace_id(organization_id, trace_id)
    if session is None:
        raise NotFoundError(f"Trace {trace_id!r} was not found in this organization.")
    spans = await repos.trace_spans.list_for_trace(organization_id, trace_id)
    data = TraceResponse(
        trace_id=trace_id,
        root_service_name=session.root_service_name,
        started_at=session.started_at,
        duration_ms=session.duration_ms,
        is_complete=session.is_complete,
        has_error=session.has_error,
        span_count=session.span_count,
        spans=[
            TraceSpanResponse(
                span_id=span.span_id,
                parent_span_id=span.parent_span_id,
                name=span.name,
                service_name=span.service_name,
                status=span.status,
                started_at=span.started_at,
                duration_ms=span.duration_ms,
                self_time_ms=span.self_time_ms,
            )
            for span in spans
        ],
    )
    return SuccessResponse(message="Trace retrieved.", data=data, meta=_meta())


# ---- GET /observability/events -----------------------------------------------------


@router.get("/events", response_model=SuccessResponse[EventsResponse], summary="Search events")
async def get_events(
    organization_id: OrganizationId,
    search: Search,
    start: datetime | None = None,
    end: datetime | None = None,
    kind: EventKind | None = None,
    service_name: str | None = None,
    cursor: str | None = None,
    page_size: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
) -> SuccessResponse[EventsResponse]:
    """Bounded, cursor-paginated event search."""
    window_start, window_end = (start, end) if start and end else _default_window(1)
    filters = tuple(
        SearchFilter(field, value)
        for field, value in (("kind", kind.value if kind else None), ("service", service_name))
        if value is not None
    )
    request = SearchRequest(
        signal_kind=SignalKind.EVENT,
        time_range=TimeRange(window_start, window_end),
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )
    result = await search.search(organization_id, request, now=datetime.now(UTC))
    validation, rows = result if isinstance(result, tuple) else (result, [])
    if not validation.is_valid:
        raise ValidationError(validation.detail or "Invalid search request.")

    page = search.paginate(validation, rows)
    data = EventsResponse(
        events=[
            ObservabilityEventResponse(
                id=row.record_id,
                event_kind=EventKind(str(row.payload["kind"])),
                severity=EventSeverity(str(row.payload.get("severity", "info"))),
                title=str(row.payload["title"]),
                occurred_at=row.occurred_at,
                ended_at=None,
                service_name=row.payload.get("service_name"),
            )
            for row in page.rows
        ],
        page=PageInfo(next_cursor=page.next_cursor, has_more=page.has_more),
    )
    return SuccessResponse(message="Events retrieved.", data=data, meta=_meta())


# ---- GET /observability/topology ---------------------------------------------------


@router.get(
    "/topology", response_model=SuccessResponse[TopologyResponse], summary="Service topology"
)
async def get_topology(
    organization_id: OrganizationId,
    repos: Repos,
    environment: str = "production",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = MAX_PAGE_SIZE,
) -> SuccessResponse[TopologyResponse]:
    """Every node and edge persisted for one environment, most critical
    nodes first."""
    nodes = await repos.topology_nodes.list_critical(organization_id, environment, limit=limit)
    edges = await repos.dependencies.list_for_environment(organization_id, environment, limit=limit)
    data = TopologyResponse(
        environment=environment,
        nodes=[
            TopologyNodeResponse(
                service_name=node.service_name,
                health=node.health,
                fan_in=node.fan_in,
                fan_out=node.fan_out,
                criticality=node.criticality,
                in_cycle=node.in_cycle,
            )
            for node in nodes
        ],
        edges=[
            TopologyEdgeResponse(
                caller_service=edge.caller_service,
                callee_service=edge.callee_service,
                call_count=edge.call_count,
                error_rate=edge.error_rate,
                confidence=edge.confidence,
                is_stale=edge.is_stale,
            )
            for edge in edges
        ],
    )
    return SuccessResponse(message="Topology retrieved.", data=data, meta=_meta())


# ---- GET/POST /observability/slos --------------------------------------------------


def _slo_response(slo: Slo) -> SloResponse:
    return SloResponse(
        id=slo.id,
        name=slo.name,
        description=slo.description,
        service_name=slo.service_name,
        environment=slo.environment,
        sli_kind=slo.sli_kind,
        target=slo.target,
        latency_threshold_ms=slo.latency_threshold_ms,
        window_days=slo.window_days,
        is_rolling=slo.is_rolling,
        is_enabled=slo.is_enabled,
        owner=slo.owner,
    )


@router.get("/slos", response_model=SuccessResponse[SlosResponse], summary="List SLOs")
async def list_slos(
    organization_id: OrganizationId,
    repos: Repos,
    service_name: str | None = None,
) -> SuccessResponse[SlosResponse]:
    """Every enabled SLO for the caller's organization."""
    rows = await repos.slos.list_enabled(organization_id, service_name=service_name)
    data = SlosResponse(slos=[_slo_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="SLOs retrieved.", data=data, meta=_meta())


@router.post(
    "/slos",
    response_model=SuccessResponse[SloResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an SLO",
    dependencies=[Depends(require_administrator)],
)
async def create_slo(
    organization_id: OrganizationId,
    repos: Repos,
    body: SloCreateRequest,
    _actor: CurrentUserId,
) -> SuccessResponse[SloResponse]:
    """Create an SLO. Requires an administrator role.

    Burn-rate thresholds are left at :class:`Slo`'s own defaults
    (14.4x fast / 6x slow, the canonical two-window budget-share
    thresholds) -- they are a well-known convention, not a per-request
    decision most callers have an informed opinion about.
    """
    row = await repos.slos.create(
        Slo(
            organization_id=organization_id,
            name=body.name,
            description=body.description,
            service_name=body.service_name,
            environment=body.environment,
            sli_kind=body.sli_kind,
            target=body.target,
            latency_threshold_ms=body.latency_threshold_ms,
            window_days=body.window_days,
            is_rolling=body.is_rolling,
            owner=body.owner,
        )
    )
    return SuccessResponse(message="SLO created.", data=_slo_response(row), meta=_meta())


# ---- GET /observability/anomalies --------------------------------------------------


@router.get(
    "/anomalies", response_model=SuccessResponse[AnomaliesResponse], summary="List anomalies"
)
async def list_anomalies(
    organization_id: OrganizationId,
    repos: Repos,
    since: datetime | None = None,
    service_name: str | None = None,
    min_severity: AnomalySeverity | None = None,
    unacknowledged_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[AnomaliesResponse]:
    """Recent anomaly detections, most severe and most recent first."""
    window_start = since or _default_window(7)[0]
    rows = await repos.anomalies.list_recent(
        organization_id,
        since=window_start,
        service_name=service_name,
        min_severity=min_severity,
        unacknowledged_only=unacknowledged_only,
        limit=limit,
    )
    data = AnomaliesResponse(
        anomalies=[
            AnomalyResponse(
                id=row.id,
                metric_name=row.metric_name,
                service_name=row.service_name,
                detected_at=row.detected_at,
                occurred_at=row.occurred_at,
                method=row.method,
                shape=row.shape,
                severity=row.severity,
                observed_value=row.observed_value,
                expected_value=row.expected_value,
                deviation=row.deviation,
                rationale=row.rationale,
                is_acknowledged=row.is_acknowledged,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Anomalies retrieved.", data=data, meta=_meta())


# ---- GET /observability/root-cause -------------------------------------------------


@router.get(
    "/root-cause",
    response_model=SuccessResponse[RootCausesResponse],
    summary="List root cause reports",
)
async def list_root_causes(
    organization_id: OrganizationId,
    repos: Repos,
    service_name: str,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> SuccessResponse[RootCausesResponse]:
    """Root cause reports for one service, most recent first."""
    rows = await repos.root_causes.list_for_service(organization_id, service_name, limit=limit)
    data = RootCausesResponse(
        reports=[
            RootCauseResponse(
                id=row.id,
                service_name=row.service_name,
                incident_reference=row.incident_reference,
                analysed_at=row.analysed_at,
                confidence=row.confidence,
                is_conclusive=row.is_conclusive,
                summary=row.summary,
                candidates=[
                    RootCauseCandidateResponse(
                        service=c["service"],
                        rank=c["rank"],
                        tier=c["tier"],
                        distinguishable=c["distinguishable"],
                        correlation=c.get("correlation"),
                        precedes_symptom=c["precedes_symptom"],
                    )
                    for c in row.candidates
                ],
                affected_service_count=row.affected_service_count,
                recommendations=row.recommendations,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Root cause reports retrieved.", data=data, meta=_meta())


# ---- GET /observability/capacity ---------------------------------------------------


@router.get(
    "/capacity", response_model=SuccessResponse[CapacityResponse], summary="Capacity forecasts"
)
async def list_capacity(
    organization_id: OrganizationId,
    repos: Repos,
    within_days: Annotated[float, Query(gt=0)] = 365.0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CapacityResponse]:
    """Forecasts projected to exhaust within *within_days*, soonest first.

    A forecast with no trend (``days_until_exhaustion is None``) never
    appears here by construction -- see
    ``CapacityForecastRepository.list_at_risk``. It is a real, persisted
    forecast, just not an at-risk one; retrieve it by resource directly
    if a full listing is needed.
    """
    rows = await repos.forecasts.list_at_risk(organization_id, within_days=within_days, limit=limit)
    data = CapacityResponse(
        forecasts=[
            CapacityForecastResponse(
                id=row.id,
                service_name=row.service_name,
                resource_kind=row.resource_kind,
                quality=row.quality,
                generated_at=row.generated_at,
                current_value=row.current_value,
                forecast_value=row.forecast_value,
                forecast_low=row.forecast_low,
                forecast_high=row.forecast_high,
                ceiling=row.ceiling,
                days_until_exhaustion=row.days_until_exhaustion,
                exhaustion_at=row.exhaustion_at,
                refusal_reason=row.refusal_reason,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Capacity forecasts retrieved.", data=data, meta=_meta())


# ---- GET /observability/cost -------------------------------------------------------


@router.get("/cost", response_model=SuccessResponse[CostResponse], summary="Cost reports")
async def list_cost(
    organization_id: OrganizationId,
    repos: Repos,
    period_start: datetime,
    period_end: datetime,
    dimension: str = "project",
) -> SuccessResponse[CostResponse]:
    """Every reported cost value at one dimension for one period."""
    rows = await repos.costs.list_for_period(
        organization_id, period_start=period_start, period_end=period_end, dimension=dimension
    )
    data = CostResponse(
        reports=[
            CostReportResponse(
                id=row.id,
                period_start=row.period_start,
                period_end=row.period_end,
                dimension=row.dimension,
                dimension_value=row.dimension_value,
                currency=row.currency,
                total_cost=row.total_cost,
                attributed_cost=row.attributed_cost,
                unattributed_cost=row.unattributed_cost,
                allocated_shared_cost=row.allocated_shared_cost,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Cost reports retrieved.", data=data, meta=_meta())


# ---- GET /observability/statistics -------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Ingestion and platform statistics",
)
async def get_statistics(
    organization_id: OrganizationId,
    repos: Repos,
    start: datetime | None = None,
    end: datetime | None = None,
) -> SuccessResponse[StatisticsResponse]:
    """Rolled-up statistic windows for the caller's organization."""
    window_start, window_end = (start, end) if start and end else _default_window(7)
    rows = await repos.statistics.list_range(organization_id, start=window_start, end=window_end)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                metrics_ingested=row.metrics_ingested,
                logs_ingested=row.logs_ingested,
                spans_ingested=row.spans_ingested,
                events_ingested=row.events_ingested,
                rejected_count=row.rejected_count,
                active_series_count=row.active_series_count,
                error_log_count=row.error_log_count,
                anomalies_detected=row.anomalies_detected,
                slos_breaching=row.slos_breaching,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


# ---- GET /observability/reports ----------------------------------------------------


@router.get(
    "/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    status_filter: Annotated[ReportStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    """Generated reports (performance, capacity, SLO, cost, audit), newest first."""
    rows = await repos.reports.list_recent(organization_id, status=status_filter, limit=limit)
    data = ReportsResponse(
        reports=[
            ReportResponse(
                id=row.id,
                kind=row.kind,
                report_format=row.report_format,
                title=row.title,
                status=row.status,
                period_start=row.period_start,
                period_end=row.period_end,
                generated_at=row.generated_at,
                row_count=row.row_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


__all__ = ["router"]
