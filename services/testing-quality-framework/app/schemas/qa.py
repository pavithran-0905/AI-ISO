"""Request/response shapes for the 11 docs/077 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CheckResultStatus,
    CoverageType,
    PerformanceTestType,
    QaReportKind,
    QualityGateStatus,
    QualityGateType,
    SecurityTestType,
    TestRunStatus,
    TestType,
)

MAX_PAGE_SIZE = 500


# ---- GET /qa/test-suites -------------------------------------------------------------------


class TestSuiteResponse(BaseModel):
    id: UUID
    name: str
    test_type: TestType
    is_enabled: bool


class TestSuitesResponse(BaseModel):
    suites: list[TestSuiteResponse]
    total: int


# ---- POST /qa/test-runs -------------------------------------------------------------------


class TestRunRequest(BaseModel):
    test_suite_id: UUID
    test_environment_id: UUID | None = None


class TestRunResponse(BaseModel):
    id: UUID
    test_suite_id: UUID
    status: TestRunStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- GET /qa/results -----------------------------------------------------------------------


class TestResultResponse(BaseModel):
    id: UUID
    test_run_id: UUID
    test_case_id: UUID
    status: str
    duration_ms: int


class TestResultsResponse(BaseModel):
    results: list[TestResultResponse]
    total: int


# ---- GET /qa/coverage ----------------------------------------------------------------------


class CoverageReportResponse(BaseModel):
    id: UUID
    coverage_type: CoverageType
    percentage: float
    lines_covered: int
    lines_total: int


class CoverageReportsResponse(BaseModel):
    reports: list[CoverageReportResponse]
    total: int


# ---- GET /qa/performance -------------------------------------------------------------------


class PerformanceResultResponse(BaseModel):
    id: UUID
    performance_type: PerformanceTestType
    latency_ms: float
    throughput_rps: float


class PerformanceResultsResponse(BaseModel):
    results: list[PerformanceResultResponse]
    total: int


# ---- GET /qa/security ----------------------------------------------------------------------


class SecurityResultResponse(BaseModel):
    id: UUID
    security_type: SecurityTestType
    status: CheckResultStatus
    findings_count: int


class SecurityResultsResponse(BaseModel):
    results: list[SecurityResultResponse]
    total: int


# ---- GET /qa/benchmarks --------------------------------------------------------------------


class BenchmarkResultResponse(BaseModel):
    id: UUID
    name: str
    baseline_value: float
    measured_value: float
    unit: str


class BenchmarkResultsResponse(BaseModel):
    results: list[BenchmarkResultResponse]
    total: int


# ---- GET/POST /qa/quality-gates -------------------------------------------------------------


class QualityGateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    gate_type: QualityGateType
    threshold: float = Field(ge=0.0)


class QualityGateResponse(BaseModel):
    id: UUID
    name: str
    gate_type: QualityGateType
    threshold: float
    status: QualityGateStatus


class QualityGatesResponse(BaseModel):
    gates: list[QualityGateResponse]
    total: int


# ---- GET /qa/reports -----------------------------------------------------------------------


class ReportResponse(BaseModel):
    id: UUID
    kind: QaReportKind
    report_format: str
    title: str
    status: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class ReportsResponse(BaseModel):
    reports: list[ReportResponse]
    total: int


# ---- GET /qa/statistics --------------------------------------------------------------------


class StatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    test_run_count: int
    pass_count: int
    fail_count: int
    flaky_count: int
    quality_gate_failure_count: int
    quality_score: float


class StatisticsResponse(BaseModel):
    windows: list[StatisticWindowResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "BenchmarkResultResponse",
    "BenchmarkResultsResponse",
    "CoverageReportResponse",
    "CoverageReportsResponse",
    "PerformanceResultResponse",
    "PerformanceResultsResponse",
    "QualityGateRequest",
    "QualityGateResponse",
    "QualityGatesResponse",
    "ReportResponse",
    "ReportsResponse",
    "SecurityResultResponse",
    "SecurityResultsResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "TestResultResponse",
    "TestResultsResponse",
    "TestRunRequest",
    "TestRunResponse",
    "TestSuiteResponse",
    "TestSuitesResponse",
]
