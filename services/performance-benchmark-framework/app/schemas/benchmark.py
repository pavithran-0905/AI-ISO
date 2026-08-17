"""Request/response shapes for the 11 docs/078 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    BenchmarkReportKind,
    BenchmarkRunStatus,
    BenchmarkType,
    OptimizationCategory,
    RecommendationStatus,
    RegressionSeverity,
    RegressionType,
    SliType,
)

MAX_PAGE_SIZE = 500


# ---- GET/POST /benchmarks, GET /benchmarks/{id} ---------------------------------------------


class BenchmarkSuiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    benchmark_type: BenchmarkType
    description: str = ""


class BenchmarkSuiteResponse(BaseModel):
    id: UUID
    name: str
    benchmark_type: BenchmarkType
    description: str
    is_enabled: bool


class BenchmarkSuitesResponse(BaseModel):
    suites: list[BenchmarkSuiteResponse]
    total: int


# ---- POST /benchmarks/run -----------------------------------------------------------------


class BenchmarkRunRequest(BaseModel):
    benchmark_suite_id: UUID
    benchmark_profile_id: UUID | None = None


class BenchmarkRunResponse(BaseModel):
    id: UUID
    benchmark_suite_id: UUID
    status: BenchmarkRunStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- GET /performance ----------------------------------------------------------------------


class PerformanceMetricResponse(BaseModel):
    id: UUID
    performance_profile_id: UUID
    metric_name: str
    value: float
    unit: str
    recorded_at: datetime


class PerformanceMetricsResponse(BaseModel):
    metrics: list[PerformanceMetricResponse]
    total: int


# ---- GET /performance/regressions -----------------------------------------------------------


class PerformanceRegressionResponse(BaseModel):
    id: UUID
    regression_type: RegressionType
    metric_name: str
    baseline_value: float
    current_value: float
    regression_percent: float
    severity: RegressionSeverity


class PerformanceRegressionsResponse(BaseModel):
    regressions: list[PerformanceRegressionResponse]
    total: int


# ---- GET /capacity --------------------------------------------------------------------------


class CapacityForecastResponse(BaseModel):
    id: UUID
    capacity_model_id: UUID
    forecast_date: datetime
    projected_value: float
    threshold_value: float


class CapacityForecastsResponse(BaseModel):
    forecasts: list[CapacityForecastResponse]
    total: int


# ---- GET /optimization -----------------------------------------------------------------------


class OptimizationRecommendationResponse(BaseModel):
    id: UUID
    category: OptimizationCategory
    title: str
    detail: str
    impact_score: float
    status: RecommendationStatus


class OptimizationRecommendationsResponse(BaseModel):
    recommendations: list[OptimizationRecommendationResponse]
    total: int


# ---- GET /slos -------------------------------------------------------------------------------


class SloResultResponse(BaseModel):
    id: UUID
    slo_name: str
    sli_type: SliType
    target_value: float
    actual_value: float
    is_compliant: bool
    evaluated_at: datetime


class SloResultsResponse(BaseModel):
    results: list[SloResultResponse]
    total: int


# ---- GET /reports ----------------------------------------------------------------------------


class BenchmarkReportResponse(BaseModel):
    id: UUID
    kind: BenchmarkReportKind
    report_format: str
    title: str
    status: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class BenchmarkReportsResponse(BaseModel):
    reports: list[BenchmarkReportResponse]
    total: int


# ---- GET /statistics -------------------------------------------------------------------------


class BenchmarkStatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    benchmark_run_count: int
    regression_count: int
    slo_violation_count: int
    avg_performance_score: float


class BenchmarkStatisticsResponse(BaseModel):
    windows: list[BenchmarkStatisticWindowResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "BenchmarkReportResponse",
    "BenchmarkReportsResponse",
    "BenchmarkRunRequest",
    "BenchmarkRunResponse",
    "BenchmarkStatisticWindowResponse",
    "BenchmarkStatisticsResponse",
    "BenchmarkSuiteRequest",
    "BenchmarkSuiteResponse",
    "BenchmarkSuitesResponse",
    "CapacityForecastResponse",
    "CapacityForecastsResponse",
    "OptimizationRecommendationResponse",
    "OptimizationRecommendationsResponse",
    "PerformanceMetricResponse",
    "PerformanceMetricsResponse",
    "PerformanceRegressionResponse",
    "PerformanceRegressionsResponse",
    "SloResultResponse",
    "SloResultsResponse",
]
