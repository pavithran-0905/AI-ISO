"""Unit/integration tests for every service, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    BenchmarkAuditAction,
    BenchmarkReportKind,
    BenchmarkType,
    LoadProfile,
    OptimizationCategory,
    RegressionType,
    ResourceType,
    SliType,
)
from app.services import benchmark_execution as benchmark_execution_services
from app.services.audit import AuditService
from app.services.baselines import BenchmarkBaselineService
from app.services.benchmark_definitions import BenchmarkProfileService, BenchmarkSuiteService
from app.services.benchmark_execution import BenchmarkResultService, BenchmarkRunService
from app.services.bundle import Repositories
from app.services.capacity import CapacityForecastService, CapacityModelService
from app.services.notifications import BenchmarkNotifier
from app.services.optimization import OptimizationRecommendationService
from app.services.performance import PerformanceMetricService, PerformanceProfileService
from app.services.regressions import PerformanceRegressionService
from app.services.reports import ReportService
from app.services.slo import SloService
from app.services.statistics import StatisticsService
from app.services.utilization import ResourceUtilizationService
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


async def _make_suite(repos: Repositories, organization_id: uuid.UUID, name: str = "s1") -> object:
    service = BenchmarkSuiteService(repos.benchmark_suites)
    return await service.create(organization_id, name=name, benchmark_type=BenchmarkType.API)


class TestBenchmarkDefinitionsServices:
    async def test_suite_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        suite = await _make_suite(repos, organization_id)
        assert suite.name == "s1"  # type: ignore[attr-defined]

    async def test_profile_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        suite = await _make_suite(repos, organization_id, name="s2")
        service = BenchmarkProfileService(repos.benchmark_profiles)
        profile = await service.create(
            organization_id, benchmark_suite_id=suite.id, name="peak", load_profile=LoadProfile.PEAK  # type: ignore[attr-defined]
        )
        assert profile.load_profile == "peak"


class TestBaselineService:
    async def test_get_or_create_initial_creates_once(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s3")
        service = BenchmarkBaselineService(repos.benchmark_baselines, publish=publisher)
        first = await service.get_or_create_initial(
            organization_id,
            benchmark_suite_id=suite.id,  # type: ignore[attr-defined]
            metric_name="latency_ms",
            value=100.0,
            unit="ms",
            higher_is_better=False,
        )
        second = await service.get_or_create_initial(
            organization_id,
            benchmark_suite_id=suite.id,  # type: ignore[attr-defined]
            metric_name="latency_ms",
            value=999.0,
            unit="ms",
            higher_is_better=False,
        )
        assert first.id == second.id
        assert second.baseline_value == 100.0
        assert "BaselineUpdated" in publisher.names()

    async def test_set_baseline_replaces_existing(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s4")
        service = BenchmarkBaselineService(repos.benchmark_baselines, publish=publisher)
        await service.set_baseline(
            organization_id,
            benchmark_suite_id=suite.id,  # type: ignore[attr-defined]
            metric_name="throughput_rps",
            baseline_value=1000.0,
            unit="rps",
            higher_is_better=True,
        )
        replaced = await service.set_baseline(
            organization_id,
            benchmark_suite_id=suite.id,  # type: ignore[attr-defined]
            metric_name="throughput_rps",
            baseline_value=1200.0,
            unit="rps",
            higher_is_better=True,
        )
        assert replaced.baseline_value == 1200.0
        assert publisher.names().count("BaselineUpdated") == 2


class TestBenchmarkExecutionServices:
    async def test_run_start_and_complete(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s5")
        service = BenchmarkRunService(repos.benchmark_runs, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        run = await service.create(organization_id, benchmark_suite_id=suite.id)  # type: ignore[attr-defined]
        run = await service.start(run, now=utcnow())
        assert "BenchmarkStarted" in publisher.names()
        completed = await service.complete(run, status="succeeded", now=utcnow())  # type: ignore[arg-type]
        assert completed.status == "succeeded"
        assert "BenchmarkCompleted" in publisher.names()
        assert any(call[0] == "notify_benchmark_completed" for call in notifier.calls)

    async def test_run_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s6")
        service = BenchmarkRunService(repos.benchmark_runs)
        run = await service.create(organization_id, benchmark_suite_id=suite.id)  # type: ignore[attr-defined]
        with pytest.raises(benchmark_execution_services.TransitionRefusedError):
            await service.complete(run, status="succeeded", now=utcnow())  # type: ignore[arg-type]

    async def test_result_record_auto_selects_baseline(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s7")
        run_service = BenchmarkRunService(repos.benchmark_runs)
        run = await run_service.create(organization_id, benchmark_suite_id=suite.id)  # type: ignore[attr-defined]
        baseline_service = BenchmarkBaselineService(repos.benchmark_baselines)
        result_service = BenchmarkResultService(repos.benchmark_results, baselines=baseline_service)
        result = await result_service.record(
            organization_id,
            benchmark_run_id=run.id,
            benchmark_suite_id=suite.id,  # type: ignore[attr-defined]
            metric_name="latency_ms",
            value=100.0,
            higher_is_better=False,
        )
        assert result.value == 100.0
        baseline = await repos.benchmark_baselines.find_by_suite_metric(
            organization_id, benchmark_suite_id=suite.id, metric_name="latency_ms"  # type: ignore[attr-defined]
        )
        assert baseline is not None
        assert baseline.baseline_value == 100.0


class TestPerformanceServices:
    async def test_profile_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = PerformanceProfileService(repos.performance_profiles)
        profile = await service.create(
            organization_id, name="api-latency", target_type=BenchmarkType.API
        )
        assert profile.name == "api-latency"

    async def test_metric_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        profile_service = PerformanceProfileService(repos.performance_profiles)
        profile = await profile_service.create(
            organization_id, name="api-latency-2", target_type=BenchmarkType.API
        )
        metric_service = PerformanceMetricService(repos.performance_metrics)
        metric = await metric_service.record(
            organization_id,
            performance_profile_id=profile.id,
            metric_name="latency_ms",
            value=42.0,
            recorded_at=utcnow(),
        )
        assert metric.value == 42.0


class TestCapacityServices:
    async def test_model_and_forecast_create(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        model_service = CapacityModelService(repos.capacity_models)
        model = await model_service.create(
            organization_id,
            name="db-storage",
            resource_type=ResourceType.STORAGE,
            growth_rate_percent=5.0,
        )
        forecast_service = CapacityForecastService(repos.capacity_forecasts)
        forecast = await forecast_service.create(
            organization_id,
            capacity_model_id=model.id,
            forecast_date=utcnow(),
            projected_value=90.0,
            threshold_value=100.0,
        )
        assert forecast.capacity_model_id == model.id


class TestOptimizationRecommendationService:
    async def test_create_non_scaling_notifies_optimization_available(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = OptimizationRecommendationService(
            repos.optimization_recommendations, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        recommendation = await service.create(
            organization_id,
            category=OptimizationCategory.QUERY,
            title="optimize slow query",
            detail="detail",
            magnitude_percent=30.0,
        )
        assert recommendation.impact_score == 30.0
        assert "OptimizationGenerated" in publisher.names()
        assert any(call[0] == "notify_optimization_available" for call in notifier.calls)

    async def test_create_scaling_notifies_scaling_recommendation(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = OptimizationRecommendationService(  # type: ignore[arg-type]
            repos.optimization_recommendations, notifier=notifier
        )
        await service.create(
            organization_id,
            category=OptimizationCategory.SCALING,
            title="scale up",
            detail="detail",
            magnitude_percent=60.0,
        )
        assert any(call[0] == "notify_scaling_recommendation" for call in notifier.calls)
        assert not any(call[0] == "notify_optimization_available" for call in notifier.calls)


class TestPerformanceRegressionService:
    async def test_record_publishes_and_computes_severity(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = PerformanceRegressionService(repos.performance_regressions, publish=publisher)
        regression = await service.record(
            organization_id,
            regression_type=RegressionType.LATENCY,
            metric_name="latency_ms",
            baseline_value=100.0,
            current_value=150.0,
            regression_percent=30.0,
            critical_threshold_percent=25.0,
        )
        assert regression.severity == "critical"
        assert "RegressionDetected" in publisher.names()


class TestResourceUtilizationService:
    async def test_record_notifies_on_bottleneck(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = ResourceUtilizationService(repos.resource_utilization, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id,
            resource_type=ResourceType.CPU,
            utilization_percent=95.0,
            recorded_at=utcnow(),
        )
        assert any(call[0] == "notify_infrastructure_bottleneck" for call in notifier.calls)

    async def test_record_no_notification_when_ok(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = ResourceUtilizationService(repos.resource_utilization, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id,
            resource_type=ResourceType.CPU,
            utilization_percent=40.0,
            recorded_at=utcnow(),
        )
        assert notifier.calls == []


class TestSloService:
    async def test_evaluate_compliant(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SloService(repos.slo_results)
        result = await service.evaluate(
            organization_id,
            slo_name="api-availability",
            sli_type=SliType.AVAILABILITY,
            target_value=99.9,
            actual_value=99.95,
            evaluated_at=utcnow(),
        )
        assert result.is_compliant is True

    async def test_evaluate_non_compliant(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SloService(repos.slo_results)
        result = await service.evaluate(
            organization_id,
            slo_name="api-latency",
            sli_type=SliType.LATENCY,
            target_value=100.0,
            actual_value=150.0,
            evaluated_at=utcnow(),
        )
        assert result.is_compliant is False


class TestStatisticsAndReportsServices:
    async def test_roll_up_window_is_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = StatisticsService(repos.statistics)
        window_start = utcnow()
        first = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            benchmark_run_count=1,
            regression_count=0,
            slo_violation_count=0,
            avg_performance_score=0.9,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            benchmark_run_count=5,
            regression_count=1,
            slo_violation_count=0,
            avg_performance_score=0.8,
        )
        assert first.id == second.id
        assert second.benchmark_run_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=BenchmarkReportKind.BENCHMARK,
            title="Weekly benchmark report",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=10,
            now=utcnow(),
        )
        assert report.status == "completed"
        assert report.row_count == 10


class TestAuditService:
    async def test_record_and_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=BenchmarkAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"


class TestBenchmarkNotifierSanity:
    def test_notifier_class_importable(self) -> None:
        assert BenchmarkNotifier is not None
