"""The 11 docs/078 REST endpoints.

**Every route requires an administrator role** -- see
``app.api.deps``'s own module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from shared_core.logging.context import get_log_context

from app.api.deps import (
    BenchmarkRunServiceDep,
    BenchmarkSuiteServiceDep,
    OrganizationId,
    Repos,
    require_administrator,
)
from app.models.benchmark_definitions import BenchmarkSuite
from app.models.benchmark_execution import BenchmarkRun
from app.models.capacity import CapacityForecast
from app.models.optimization import OptimizationRecommendation
from app.models.performance import PerformanceMetric
from app.models.regressions import PerformanceRegression
from app.models.reporting import BenchmarkReport
from app.models.slo import SloResult
from app.schemas.benchmark import (
    MAX_PAGE_SIZE,
    BenchmarkReportResponse,
    BenchmarkReportsResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    BenchmarkStatisticsResponse,
    BenchmarkStatisticWindowResponse,
    BenchmarkSuiteRequest,
    BenchmarkSuiteResponse,
    BenchmarkSuitesResponse,
    CapacityForecastResponse,
    CapacityForecastsResponse,
    OptimizationRecommendationResponse,
    OptimizationRecommendationsResponse,
    PerformanceMetricResponse,
    PerformanceMetricsResponse,
    PerformanceRegressionResponse,
    PerformanceRegressionsResponse,
    SloResultResponse,
    SloResultsResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.statistics import StatisticsService

router = APIRouter(tags=["Performance & Benchmark"], dependencies=[Depends(require_administrator)])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _suite_response(suite: BenchmarkSuite) -> BenchmarkSuiteResponse:
    return BenchmarkSuiteResponse(
        id=suite.id,
        name=suite.name,
        benchmark_type=suite.benchmark_type,
        description=suite.description,
        is_enabled=suite.is_enabled,
    )


def _run_response(run: BenchmarkRun) -> BenchmarkRunResponse:
    return BenchmarkRunResponse(
        id=run.id,
        benchmark_suite_id=run.benchmark_suite_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _metric_response(metric: PerformanceMetric) -> PerformanceMetricResponse:
    return PerformanceMetricResponse(
        id=metric.id,
        performance_profile_id=metric.performance_profile_id,
        metric_name=metric.metric_name,
        value=metric.value,
        unit=metric.unit,
        recorded_at=metric.recorded_at,
    )


def _regression_response(regression: PerformanceRegression) -> PerformanceRegressionResponse:
    return PerformanceRegressionResponse(
        id=regression.id,
        regression_type=regression.regression_type,
        metric_name=regression.metric_name,
        baseline_value=regression.baseline_value,
        current_value=regression.current_value,
        regression_percent=regression.regression_percent,
        severity=regression.severity,
    )


def _forecast_response(forecast: CapacityForecast) -> CapacityForecastResponse:
    return CapacityForecastResponse(
        id=forecast.id,
        capacity_model_id=forecast.capacity_model_id,
        forecast_date=forecast.forecast_date,
        projected_value=forecast.projected_value,
        threshold_value=forecast.threshold_value,
    )


def _optimization_response(
    recommendation: OptimizationRecommendation,
) -> OptimizationRecommendationResponse:
    return OptimizationRecommendationResponse(
        id=recommendation.id,
        category=recommendation.category,
        title=recommendation.title,
        detail=recommendation.detail,
        impact_score=recommendation.impact_score,
        status=recommendation.status,
    )


def _slo_response(result: SloResult) -> SloResultResponse:
    return SloResultResponse(
        id=result.id,
        slo_name=result.slo_name,
        sli_type=result.sli_type,
        target_value=result.target_value,
        actual_value=result.actual_value,
        is_compliant=result.is_compliant,
        evaluated_at=result.evaluated_at,
    )


def _report_response(report: BenchmarkReport) -> BenchmarkReportResponse:
    return BenchmarkReportResponse(
        id=report.id,
        kind=report.kind,
        report_format=str(report.report_format),
        title=report.title,
        status=str(report.status),
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        row_count=report.row_count,
    )


# ---- GET /benchmarks -------------------------------------------------------------------


@router.get(
    "/benchmarks",
    response_model=SuccessResponse[BenchmarkSuitesResponse],
    summary="List benchmark suites",
)
async def list_benchmarks(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[BenchmarkSuitesResponse]:
    rows = await repos.benchmark_suites.list_all(organization_id, limit=limit)
    data = BenchmarkSuitesResponse(suites=[_suite_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Benchmark suites retrieved.", data=data, meta=_meta())


# ---- POST /benchmarks ------------------------------------------------------------------


@router.post(
    "/benchmarks",
    response_model=SuccessResponse[BenchmarkSuiteResponse],
    summary="Create a benchmark suite",
)
async def create_benchmark(
    organization_id: OrganizationId, service: BenchmarkSuiteServiceDep, body: BenchmarkSuiteRequest
) -> SuccessResponse[BenchmarkSuiteResponse]:
    suite = await service.create(
        organization_id,
        name=body.name,
        benchmark_type=body.benchmark_type,
        description=body.description,
    )
    return SuccessResponse(
        message="Benchmark suite created.", data=_suite_response(suite), meta=_meta()
    )


# ---- GET /benchmarks/{id} ---------------------------------------------------------------


@router.get(
    "/benchmarks/{benchmark_suite_id}",
    response_model=SuccessResponse[BenchmarkSuiteResponse],
    summary="Get a benchmark suite by id",
)
async def get_benchmark(
    benchmark_suite_id: UUID, repos: Repos
) -> SuccessResponse[BenchmarkSuiteResponse]:
    suite = await repos.benchmark_suites.require_by_id(benchmark_suite_id)
    return SuccessResponse(
        message="Benchmark suite retrieved.", data=_suite_response(suite), meta=_meta()
    )


# ---- POST /benchmarks/run --------------------------------------------------------------


@router.post(
    "/benchmarks/run",
    response_model=SuccessResponse[BenchmarkRunResponse],
    summary="Start a benchmark run",
)
async def run_benchmark(
    organization_id: OrganizationId, service: BenchmarkRunServiceDep, body: BenchmarkRunRequest
) -> SuccessResponse[BenchmarkRunResponse]:
    run = await service.create(
        organization_id,
        benchmark_suite_id=body.benchmark_suite_id,
        benchmark_profile_id=body.benchmark_profile_id,
    )
    run = await service.start(run, now=datetime.now(UTC))
    return SuccessResponse(message="Benchmark run started.", data=_run_response(run), meta=_meta())


# ---- GET /performance ------------------------------------------------------------------


@router.get(
    "/performance",
    response_model=SuccessResponse[PerformanceMetricsResponse],
    summary="List performance metrics",
)
async def list_performance(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[PerformanceMetricsResponse]:
    rows = await repos.performance_metrics.list_recent(organization_id, limit=limit)
    data = PerformanceMetricsResponse(
        metrics=[_metric_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Performance metrics retrieved.", data=data, meta=_meta())


# ---- GET /performance/regressions -------------------------------------------------------


@router.get(
    "/performance/regressions",
    response_model=SuccessResponse[PerformanceRegressionsResponse],
    summary="List detected performance regressions",
)
async def list_regressions(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[PerformanceRegressionsResponse]:
    rows = await repos.performance_regressions.list_all(organization_id, limit=limit)
    data = PerformanceRegressionsResponse(
        regressions=[_regression_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Performance regressions retrieved.", data=data, meta=_meta())


# ---- GET /capacity ---------------------------------------------------------------------


@router.get(
    "/capacity",
    response_model=SuccessResponse[CapacityForecastsResponse],
    summary="List capacity forecasts",
)
async def list_capacity(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CapacityForecastsResponse]:
    rows = await repos.capacity_forecasts.list_all(organization_id, limit=limit)
    data = CapacityForecastsResponse(
        forecasts=[_forecast_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Capacity forecasts retrieved.", data=data, meta=_meta())


# ---- GET /optimization -------------------------------------------------------------------


@router.get(
    "/optimization",
    response_model=SuccessResponse[OptimizationRecommendationsResponse],
    summary="List optimization recommendations",
)
async def list_optimization(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[OptimizationRecommendationsResponse]:
    rows = await repos.optimization_recommendations.list_all(organization_id, limit=limit)
    data = OptimizationRecommendationsResponse(
        recommendations=[_optimization_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(
        message="Optimization recommendations retrieved.", data=data, meta=_meta()
    )


# ---- GET /slos --------------------------------------------------------------------------


@router.get(
    "/slos",
    response_model=SuccessResponse[SloResultsResponse],
    summary="List SLO/SLI compliance results",
)
async def list_slos(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SloResultsResponse]:
    rows = await repos.slo_results.list_all(organization_id, limit=limit)
    data = SloResultsResponse(results=[_slo_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="SLO results retrieved.", data=data, meta=_meta())


# ---- GET /reports -----------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=SuccessResponse[BenchmarkReportsResponse],
    summary="Generated benchmark reports",
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[BenchmarkReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = BenchmarkReportsResponse(
        reports=[_report_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


# ---- GET /statistics --------------------------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[BenchmarkStatisticsResponse],
    summary="Benchmark activity statistics",
)
async def statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[BenchmarkStatisticsResponse]:
    service = StatisticsService(repos.statistics)
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await service.list_range(organization_id, since=window_since)
    data = BenchmarkStatisticsResponse(
        windows=[
            BenchmarkStatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                benchmark_run_count=row.benchmark_run_count,
                regression_count=row.regression_count,
                slo_violation_count=row.slo_violation_count,
                avg_performance_score=row.avg_performance_score,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


__all__ = ["router"]
