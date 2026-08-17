"""Repository tests, against real PostgreSQL, exercising every custom
method (not the generic CRUD ``BaseRepository`` already provides)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.models.baselines import BenchmarkBaseline
from app.models.benchmark_definitions import BenchmarkProfile, BenchmarkSuite
from app.models.benchmark_execution import BenchmarkResult, BenchmarkRun
from app.models.capacity import CapacityForecast, CapacityModel
from app.models.enums import (
    BenchmarkRunStatus,
    BenchmarkType,
    LoadProfile,
    OptimizationCategory,
    RecommendationStatus,
    RegressionSeverity,
    RegressionType,
    ResourceType,
    SliType,
)
from app.models.optimization import OptimizationRecommendation
from app.models.performance import PerformanceMetric, PerformanceProfile
from app.models.regressions import PerformanceRegression
from app.models.reporting import BenchmarkAudit, BenchmarkReport, BenchmarkStatistic
from app.models.slo import SloResult
from app.models.statistics_tables import LatencyStatistics, ThroughputStatistics
from app.models.utilization import ResourceUtilization
from app.services.bundle import Repositories
from tests.conftest import hours_ago, utcnow


class TestBenchmarkDefinitionsRepositories:
    async def test_suite_find_by_name(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="api-suite", benchmark_type=BenchmarkType.API
            )
        )
        found = await repos.benchmark_suites.find_by_name(organization_id, name="api-suite")
        assert found is not None
        assert found.benchmark_type == "api"

    async def test_suite_list_all(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s1", benchmark_type=BenchmarkType.DATABASE
            )
        )
        rows = await repos.benchmark_suites.list_all(organization_id)
        assert len(rows) == 1

    async def test_profile_list_for_suite(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s2", benchmark_type=BenchmarkType.WORKFLOW
            )
        )
        await repos.benchmark_profiles.create(
            BenchmarkProfile(
                organization_id=organization_id,
                benchmark_suite_id=suite.id,
                name="peak",
                load_profile=LoadProfile.PEAK,
            )
        )
        rows = await repos.benchmark_profiles.list_for_suite(suite.id)
        assert len(rows) == 1
        assert rows[0].load_profile == "peak"


class TestBenchmarkExecutionRepositories:
    async def test_run_list_recent_and_running(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s3", benchmark_type=BenchmarkType.API
            )
        )
        await repos.benchmark_runs.create(
            BenchmarkRun(
                organization_id=organization_id,
                benchmark_suite_id=suite.id,
                status=BenchmarkRunStatus.RUNNING,
            )
        )
        recent = await repos.benchmark_runs.list_recent(organization_id)
        assert len(recent) == 1
        running = await repos.benchmark_runs.list_running(organization_id)
        assert len(running) == 1

    async def test_run_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s4", benchmark_type=BenchmarkType.API
            )
        )
        await repos.benchmark_runs.create(
            BenchmarkRun(organization_id=organization_id, benchmark_suite_id=suite.id)
        )
        org_ids = await repos.benchmark_runs.list_organization_ids()
        assert organization_id in org_ids

    async def test_result_list_for_run_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s5", benchmark_type=BenchmarkType.API
            )
        )
        run = await repos.benchmark_runs.create(
            BenchmarkRun(organization_id=organization_id, benchmark_suite_id=suite.id)
        )
        await repos.benchmark_results.create(
            BenchmarkResult(
                organization_id=organization_id,
                benchmark_run_id=run.id,
                metric_name="latency_ms",
                value=100.0,
            )
        )
        for_run = await repos.benchmark_results.list_for_run(run.id)
        assert len(for_run) == 1
        recent = await repos.benchmark_results.list_recent(organization_id)
        assert len(recent) == 1
        org_ids = await repos.benchmark_results.list_organization_ids()
        assert organization_id in org_ids

    async def test_result_distinct_suite_metric_pairs_and_latest(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s6", benchmark_type=BenchmarkType.API
            )
        )
        run = await repos.benchmark_runs.create(
            BenchmarkRun(organization_id=organization_id, benchmark_suite_id=suite.id)
        )
        await repos.benchmark_results.create(
            BenchmarkResult(
                organization_id=organization_id,
                benchmark_run_id=run.id,
                metric_name="latency_ms",
                value=100.0,
            )
        )
        await repos.benchmark_results.create(
            BenchmarkResult(
                organization_id=organization_id,
                benchmark_run_id=run.id,
                metric_name="latency_ms",
                value=150.0,
            )
        )
        pairs = await repos.benchmark_results.list_distinct_suite_metric_pairs(organization_id)
        assert (suite.id, "latency_ms") in pairs

        latest = await repos.benchmark_results.list_latest_by_suite_metric(
            organization_id, benchmark_suite_id=suite.id, metric_name="latency_ms", limit=1
        )
        assert len(latest) == 1
        assert latest[0].value == 150.0


class TestBaselineRepository:
    async def test_find_by_suite_metric_and_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="s7", benchmark_type=BenchmarkType.API
            )
        )
        await repos.benchmark_baselines.create(
            BenchmarkBaseline(
                organization_id=organization_id,
                benchmark_suite_id=suite.id,
                metric_name="latency_ms",
                baseline_value=100.0,
                higher_is_better=False,
            )
        )
        found = await repos.benchmark_baselines.find_by_suite_metric(
            organization_id, benchmark_suite_id=suite.id, metric_name="latency_ms"
        )
        assert found is not None
        assert found.baseline_value == 100.0
        rows = await repos.benchmark_baselines.list_all(organization_id)
        assert len(rows) == 1


class TestPerformanceRepositories:
    async def test_profile_list_all(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await repos.performance_profiles.create(
            PerformanceProfile(
                organization_id=organization_id, name="api-profile", target_type=BenchmarkType.API
            )
        )
        rows = await repos.performance_profiles.list_all(organization_id)
        assert len(rows) == 1

    async def test_metric_list_recent_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.performance_profiles.create(
            PerformanceProfile(
                organization_id=organization_id, name="api-profile-2", target_type=BenchmarkType.API
            )
        )
        await repos.performance_metrics.create(
            PerformanceMetric(
                organization_id=organization_id,
                performance_profile_id=profile.id,
                metric_name="latency_ms",
                value=50.0,
                recorded_at=utcnow(),
            )
        )
        rows = await repos.performance_metrics.list_recent(organization_id)
        assert len(rows) == 1
        org_ids = await repos.performance_metrics.list_organization_ids()
        assert organization_id in org_ids


class TestCapacityRepositories:
    async def test_model_list_all(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await repos.capacity_models.create(
            CapacityModel(
                organization_id=organization_id,
                name="db-storage",
                resource_type=ResourceType.STORAGE,
                growth_rate_percent=5.0,
            )
        )
        rows = await repos.capacity_models.list_all(organization_id)
        assert len(rows) == 1

    async def test_forecast_methods(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        model = await repos.capacity_models.create(
            CapacityModel(
                organization_id=organization_id,
                name="db-storage-2",
                resource_type=ResourceType.STORAGE,
                growth_rate_percent=5.0,
            )
        )
        await repos.capacity_forecasts.create(
            CapacityForecast(
                organization_id=organization_id,
                capacity_model_id=model.id,
                forecast_date=utcnow(),
                projected_value=90.0,
                threshold_value=100.0,
            )
        )
        rows = await repos.capacity_forecasts.list_all(organization_id)
        assert len(rows) == 1
        latest = await repos.capacity_forecasts.list_latest_by_model(
            organization_id, capacity_model_id=model.id
        )
        assert len(latest) == 1
        model_ids = await repos.capacity_forecasts.list_distinct_model_ids(organization_id)
        assert model.id in model_ids
        org_ids = await repos.capacity_forecasts.list_organization_ids()
        assert organization_id in org_ids


class TestOptimizationRepository:
    async def test_list_all_and_by_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.optimization_recommendations.create(
            OptimizationRecommendation(
                organization_id=organization_id,
                category=OptimizationCategory.QUERY,
                title="optimize query",
                impact_score=50.0,
            )
        )
        rows = await repos.optimization_recommendations.list_all(organization_id)
        assert len(rows) == 1
        pending = await repos.optimization_recommendations.list_by_status(
            organization_id, status=RecommendationStatus.PENDING
        )
        assert len(pending) == 1


class TestRegressionsRepository:
    async def test_list_all_and_count_since(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.performance_regressions.create(
            PerformanceRegression(
                organization_id=organization_id,
                regression_type=RegressionType.LATENCY,
                metric_name="latency_ms",
                baseline_value=100.0,
                current_value=150.0,
                regression_percent=50.0,
                severity=RegressionSeverity.HIGH,
            )
        )
        rows = await repos.performance_regressions.list_all(organization_id)
        assert len(rows) == 1
        count = await repos.performance_regressions.count_since(
            organization_id, since=hours_ago(1), until=utcnow() + timedelta(hours=1)
        )
        assert count == 1


class TestUtilizationRepository:
    async def test_list_all_and_by_type(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.resource_utilization.create(
            ResourceUtilization(
                organization_id=organization_id,
                resource_type=ResourceType.CPU,
                utilization_percent=80.0,
                recorded_at=utcnow(),
            )
        )
        rows = await repos.resource_utilization.list_all(organization_id)
        assert len(rows) == 1
        by_type = await repos.resource_utilization.list_recent_by_type(
            organization_id, resource_type=ResourceType.CPU
        )
        assert len(by_type) == 1


class TestStatisticsTablesRepositories:
    async def test_latency_and_throughput_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.latency_statistics.create(
            LatencyStatistics(
                organization_id=organization_id,
                target_name="api",
                p50_ms=10.0,
                p95_ms=20.0,
                p99_ms=30.0,
                max_ms=40.0,
                window_start=hours_ago(1),
                window_end=utcnow(),
            )
        )
        await repos.throughput_statistics.create(
            ThroughputStatistics(
                organization_id=organization_id,
                target_name="api",
                requests_per_second=100.0,
                window_start=hours_ago(1),
                window_end=utcnow(),
            )
        )
        latency_rows = await repos.latency_statistics.list_all(organization_id)
        assert len(latency_rows) == 1
        throughput_rows = await repos.throughput_statistics.list_all(organization_id)
        assert len(throughput_rows) == 1


class TestSloRepository:
    async def test_all_methods(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await repos.slo_results.create(
            SloResult(
                organization_id=organization_id,
                slo_name="api-availability",
                sli_type=SliType.AVAILABILITY,
                target_value=99.9,
                actual_value=99.5,
                is_compliant=False,
                evaluated_at=utcnow(),
            )
        )
        rows = await repos.slo_results.list_all(organization_id)
        assert len(rows) == 1
        latest = await repos.slo_results.list_latest_by_name(
            organization_id, slo_name="api-availability"
        )
        assert len(latest) == 1
        names = await repos.slo_results.list_distinct_names(organization_id)
        assert "api-availability" in names
        org_ids = await repos.slo_results.list_organization_ids()
        assert organization_id in org_ids


class TestReportingRepositories:
    async def test_statistic_find_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = hours_ago(1)
        await repos.statistics.create(
            BenchmarkStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=utcnow(),
                benchmark_run_count=5,
                regression_count=1,
                slo_violation_count=0,
                avg_performance_score=0.9,
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        rows = await repos.statistics.list_range(organization_id, since=hours_ago(2))
        assert len(rows) == 1

    async def test_report_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.models.enums import BenchmarkReportKind, ReportStatus

        await repos.reports.create(
            BenchmarkReport(
                organization_id=organization_id,
                kind=BenchmarkReportKind.BENCHMARK,
                title="Weekly benchmark report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        rows = await repos.reports.list_recent(organization_id)
        assert len(rows) == 1
        by_kind = await repos.reports.list_recent(
            organization_id, kind=BenchmarkReportKind.BENCHMARK
        )
        assert len(by_kind) == 1

    async def test_audit_list_recent_and_for_entity(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.models.enums import BenchmarkAuditAction

        entity_id = uuid.uuid4()
        await repos.audit.create(
            BenchmarkAudit(
                organization_id=organization_id,
                action=BenchmarkAuditAction.BENCHMARK_EXECUTION,
                entity_type="benchmark_run",
                entity_id=entity_id,
                summary="ran a benchmark",
                occurred_at=utcnow(),
            )
        )
        rows = await repos.audit.list_recent(organization_id)
        assert len(rows) == 1
        for_entity = await repos.audit.list_for_entity("benchmark_run", entity_id)
        assert len(for_entity) == 1
