"""The repository bundle every route works through.

One object rather than eighteen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.baselines import BenchmarkBaselineRepository
from app.repositories.benchmark_definitions import (
    BenchmarkProfileRepository,
    BenchmarkSuiteRepository,
)
from app.repositories.benchmark_execution import BenchmarkResultRepository, BenchmarkRunRepository
from app.repositories.capacity import CapacityForecastRepository, CapacityModelRepository
from app.repositories.optimization import OptimizationRecommendationRepository
from app.repositories.performance import PerformanceMetricRepository, PerformanceProfileRepository
from app.repositories.regressions import PerformanceRegressionRepository
from app.repositories.reporting import (
    BenchmarkAuditRepository,
    BenchmarkReportRepository,
    BenchmarkStatisticRepository,
)
from app.repositories.slo import SloResultRepository
from app.repositories.statistics_tables import (
    LatencyStatisticsRepository,
    ThroughputStatisticsRepository,
)
from app.repositories.utilization import ResourceUtilizationRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    benchmark_suites: BenchmarkSuiteRepository
    benchmark_profiles: BenchmarkProfileRepository

    benchmark_runs: BenchmarkRunRepository
    benchmark_results: BenchmarkResultRepository

    benchmark_baselines: BenchmarkBaselineRepository

    performance_profiles: PerformanceProfileRepository
    performance_metrics: PerformanceMetricRepository

    capacity_models: CapacityModelRepository
    capacity_forecasts: CapacityForecastRepository

    optimization_recommendations: OptimizationRecommendationRepository

    performance_regressions: PerformanceRegressionRepository

    resource_utilization: ResourceUtilizationRepository

    latency_statistics: LatencyStatisticsRepository
    throughput_statistics: ThroughputStatisticsRepository

    slo_results: SloResultRepository

    statistics: BenchmarkStatisticRepository
    reports: BenchmarkReportRepository
    audit: BenchmarkAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        benchmark_suites=BenchmarkSuiteRepository(session, tenant_scope=tenant_scope),
        benchmark_profiles=BenchmarkProfileRepository(session, tenant_scope=tenant_scope),
        benchmark_runs=BenchmarkRunRepository(session, tenant_scope=tenant_scope),
        benchmark_results=BenchmarkResultRepository(session, tenant_scope=tenant_scope),
        benchmark_baselines=BenchmarkBaselineRepository(session, tenant_scope=tenant_scope),
        performance_profiles=PerformanceProfileRepository(session, tenant_scope=tenant_scope),
        performance_metrics=PerformanceMetricRepository(session, tenant_scope=tenant_scope),
        capacity_models=CapacityModelRepository(session, tenant_scope=tenant_scope),
        capacity_forecasts=CapacityForecastRepository(session, tenant_scope=tenant_scope),
        optimization_recommendations=OptimizationRecommendationRepository(
            session, tenant_scope=tenant_scope
        ),
        performance_regressions=PerformanceRegressionRepository(session, tenant_scope=tenant_scope),
        resource_utilization=ResourceUtilizationRepository(session, tenant_scope=tenant_scope),
        latency_statistics=LatencyStatisticsRepository(session, tenant_scope=tenant_scope),
        throughput_statistics=ThroughputStatisticsRepository(session, tenant_scope=tenant_scope),
        slo_results=SloResultRepository(session, tenant_scope=tenant_scope),
        statistics=BenchmarkStatisticRepository(session, tenant_scope=tenant_scope),
        reports=BenchmarkReportRepository(session, tenant_scope=tenant_scope),
        audit=BenchmarkAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
