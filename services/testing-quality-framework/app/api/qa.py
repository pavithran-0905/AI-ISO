"""The 11 docs/077 REST endpoints.

**Every route requires an administrator role** -- see
``app.api.deps``'s own module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from shared_core.logging.context import get_log_context

from app.api.deps import (
    OrganizationId,
    QualityGateServiceDep,
    Repos,
    TestRunServiceDep,
    require_administrator,
)
from app.models.performance import BenchmarkResult, PerformanceResult
from app.models.quality_gates import QualityGate
from app.models.reporting import QaReport
from app.models.security_chaos import SecurityResult
from app.models.test_definitions import TestSuite
from app.models.test_execution import TestResult, TestRun
from app.schemas.qa import (
    MAX_PAGE_SIZE,
    BenchmarkResultResponse,
    BenchmarkResultsResponse,
    CoverageReportResponse,
    CoverageReportsResponse,
    PerformanceResultResponse,
    PerformanceResultsResponse,
    QualityGateRequest,
    QualityGateResponse,
    QualityGatesResponse,
    ReportResponse,
    ReportsResponse,
    SecurityResultResponse,
    SecurityResultsResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    TestResultResponse,
    TestResultsResponse,
    TestRunRequest,
    TestRunResponse,
    TestSuiteResponse,
    TestSuitesResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.statistics import StatisticsService

router = APIRouter(
    tags=["Testing & Quality Assurance"], dependencies=[Depends(require_administrator)]
)


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _suite_response(suite: TestSuite) -> TestSuiteResponse:
    return TestSuiteResponse(
        id=suite.id, name=suite.name, test_type=suite.test_type, is_enabled=suite.is_enabled
    )


def _run_response(run: TestRun) -> TestRunResponse:
    return TestRunResponse(
        id=run.id,
        test_suite_id=run.test_suite_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _result_response(result: TestResult) -> TestResultResponse:
    return TestResultResponse(
        id=result.id,
        test_run_id=result.test_run_id,
        test_case_id=result.test_case_id,
        status=str(result.status),
        duration_ms=result.duration_ms,
    )


def _security_response(result: SecurityResult) -> SecurityResultResponse:
    return SecurityResultResponse(
        id=result.id,
        security_type=result.security_type,
        status=result.status,
        findings_count=result.findings_count,
    )


def _benchmark_response(result: BenchmarkResult) -> BenchmarkResultResponse:
    return BenchmarkResultResponse(
        id=result.id,
        name=result.name,
        baseline_value=result.baseline_value,
        measured_value=result.measured_value,
        unit=result.unit,
    )


def _performance_response(result: PerformanceResult) -> PerformanceResultResponse:
    return PerformanceResultResponse(
        id=result.id,
        performance_type=result.performance_type,
        latency_ms=result.latency_ms,
        throughput_rps=result.throughput_rps,
    )


def _quality_gate_response(gate: QualityGate) -> QualityGateResponse:
    return QualityGateResponse(
        id=gate.id,
        name=gate.name,
        gate_type=gate.gate_type,
        threshold=gate.threshold,
        status=gate.status,
    )


def _report_response(report: QaReport) -> ReportResponse:
    return ReportResponse(
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


# ---- GET /qa/test-suites -------------------------------------------------------------------


@router.get(
    "/qa/test-suites",
    response_model=SuccessResponse[TestSuitesResponse],
    summary="List test suites",
)
async def list_test_suites(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[TestSuitesResponse]:
    rows = await repos.test_suites.list_all(organization_id, limit=limit)
    data = TestSuitesResponse(suites=[_suite_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Test suites retrieved.", data=data, meta=_meta())


# ---- POST /qa/test-runs -------------------------------------------------------------------


@router.post(
    "/qa/test-runs", response_model=SuccessResponse[TestRunResponse], summary="Start a test run"
)
async def start_test_run(
    organization_id: OrganizationId, service: TestRunServiceDep, body: TestRunRequest
) -> SuccessResponse[TestRunResponse]:
    run = await service.create(
        organization_id,
        test_suite_id=body.test_suite_id,
        test_environment_id=body.test_environment_id,
    )
    run = await service.start(run, now=datetime.now(UTC))
    return SuccessResponse(message="Test run started.", data=_run_response(run), meta=_meta())


# ---- GET /qa/results -----------------------------------------------------------------------


@router.get(
    "/qa/results",
    response_model=SuccessResponse[TestResultsResponse],
    summary="List recent test results",
)
async def list_results(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[TestResultsResponse]:
    rows = await repos.test_results.list_recent(organization_id, limit=limit)
    data = TestResultsResponse(results=[_result_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Test results retrieved.", data=data, meta=_meta())


# ---- GET /qa/coverage ----------------------------------------------------------------------


@router.get(
    "/qa/coverage",
    response_model=SuccessResponse[CoverageReportsResponse],
    summary="List coverage reports",
)
async def list_coverage(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CoverageReportsResponse]:
    rows = await repos.coverage_reports.list_all(organization_id, limit=limit)
    data = CoverageReportsResponse(
        reports=[
            CoverageReportResponse(
                id=row.id,
                coverage_type=row.coverage_type,
                percentage=row.percentage,
                lines_covered=row.lines_covered,
                lines_total=row.lines_total,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Coverage reports retrieved.", data=data, meta=_meta())


# ---- GET /qa/performance -------------------------------------------------------------------


@router.get(
    "/qa/performance",
    response_model=SuccessResponse[PerformanceResultsResponse],
    summary="List performance results",
)
async def list_performance(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[PerformanceResultsResponse]:
    rows = await repos.performance_results.list_all(organization_id, limit=limit)
    data = PerformanceResultsResponse(
        results=[_performance_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Performance results retrieved.", data=data, meta=_meta())


# ---- GET /qa/security ----------------------------------------------------------------------


@router.get(
    "/qa/security",
    response_model=SuccessResponse[SecurityResultsResponse],
    summary="List security test results",
)
async def list_security(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SecurityResultsResponse]:
    rows = await repos.security_results.list_all(organization_id, limit=limit)
    data = SecurityResultsResponse(
        results=[_security_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Security results retrieved.", data=data, meta=_meta())


# ---- GET /qa/benchmarks --------------------------------------------------------------------


@router.get(
    "/qa/benchmarks",
    response_model=SuccessResponse[BenchmarkResultsResponse],
    summary="List benchmark results",
)
async def list_benchmarks(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[BenchmarkResultsResponse]:
    rows = await repos.benchmark_results.list_all(organization_id, limit=limit)
    data = BenchmarkResultsResponse(
        results=[_benchmark_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Benchmark results retrieved.", data=data, meta=_meta())


# ---- GET/POST /qa/quality-gates -------------------------------------------------------------


@router.get(
    "/qa/quality-gates",
    response_model=SuccessResponse[QualityGatesResponse],
    summary="List quality gates",
)
async def list_quality_gates(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[QualityGatesResponse]:
    rows = await repos.quality_gates.list_all(organization_id, limit=limit)
    data = QualityGatesResponse(
        gates=[_quality_gate_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Quality gates retrieved.", data=data, meta=_meta())


@router.post(
    "/qa/quality-gates",
    response_model=SuccessResponse[QualityGateResponse],
    summary="Define a new quality gate",
)
async def create_quality_gate(
    organization_id: OrganizationId, service: QualityGateServiceDep, body: QualityGateRequest
) -> SuccessResponse[QualityGateResponse]:
    gate = await service.create(
        organization_id, name=body.name, gate_type=body.gate_type, threshold=body.threshold
    )
    return SuccessResponse(
        message="Quality gate created.", data=_quality_gate_response(gate), meta=_meta()
    )


# ---- GET /qa/reports -----------------------------------------------------------------------


@router.get(
    "/qa/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated QA reports"
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(reports=[_report_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


# ---- GET /qa/statistics --------------------------------------------------------------------


@router.get(
    "/qa/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="QA activity statistics",
)
async def statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    service = StatisticsService(repos.statistics)
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await service.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                test_run_count=row.test_run_count,
                pass_count=row.pass_count,
                fail_count=row.fail_count,
                flaky_count=row.flaky_count,
                quality_gate_failure_count=row.quality_gate_failure_count,
                quality_score=row.quality_score,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


__all__ = ["router"]
