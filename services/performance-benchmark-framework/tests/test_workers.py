"""Integration tests for every worker, against real PostgreSQL.

Each worker is exercised by calling its own ``tick()`` directly --
never through the scheduler -- matching every other service's own
worker test shape in this codebase.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.baselines import BenchmarkBaseline
from app.models.benchmark_definitions import BenchmarkSuite
from app.models.benchmark_execution import BenchmarkResult, BenchmarkRun
from app.models.capacity import CapacityForecast, CapacityModel
from app.models.enums import BenchmarkRunStatus, BenchmarkType, ResourceType, SliType
from app.models.slo import SloResult
from app.services.bundle import Repositories, build_repositories
from app.services.notifications import BenchmarkNotifier
from app.types import EventPublisher
from app.workers.benchmark_run_timeout_sweep import BenchmarkRunTimeoutSweepWorker
from app.workers.capacity_threshold_sweep import CapacityThresholdSweepWorker
from app.workers.regression_sweep import RegressionSweepWorker
from app.workers.slo_compliance_sweep import SloComplianceSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


class TestBenchmarkRunTimeoutSweepWorkerBehaviour:
    async def test_fails_stuck_run_on_next_tick(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id,
                name="worker-suite",
                benchmark_type=BenchmarkType.API,
            )
        )
        stuck_run = await repos.benchmark_runs.create(
            BenchmarkRun(
                organization_id=organization_id,
                benchmark_suite_id=suite.id,
                status=BenchmarkRunStatus.RUNNING,
                started_at=hours_ago(5),
            )
        )
        fresh_run = await repos.benchmark_runs.create(
            BenchmarkRun(
                organization_id=organization_id,
                benchmark_suite_id=suite.id,
                status=BenchmarkRunStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.commit()

        worker = BenchmarkRunTimeoutSweepWorker(db_session_factory, max_age_hours=4)
        failed = await worker.tick()
        assert failed == 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            reread_stuck = await check_repos.benchmark_runs.require_by_id(stuck_run.id)
            reread_fresh = await check_repos.benchmark_runs.require_by_id(fresh_run.id)
        assert reread_stuck.status == "failed"
        assert reread_fresh.status == "running"


class TestRegressionSweepWorkerBehaviour:
    async def test_detects_regression_and_creates_recommendation(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id,
                name="regress-suite",
                benchmark_type=BenchmarkType.DATABASE,
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
        run = await repos.benchmark_runs.create(
            BenchmarkRun(organization_id=organization_id, benchmark_suite_id=suite.id)
        )
        result = BenchmarkResult(
            organization_id=organization_id,
            benchmark_run_id=run.id,
            metric_name="latency_ms",
            value=150.0,
        )
        result.created_at = hours_ago(0.1)
        await repos.benchmark_results.create(result)
        await db_session.commit()

        worker = RegressionSweepWorker(
            db_session_factory,
            publish=publisher,  # type: ignore[arg-type]
            notifier=notifier,  # type: ignore[arg-type]
            warning_threshold_percent=10.0,
            critical_threshold_percent=25.0,
            improvement_threshold_percent=10.0,
            lookback_seconds=3600,
        )
        detected = await worker.tick()
        assert detected == 1
        assert "RegressionDetected" in publisher.names()
        assert "OptimizationGenerated" in publisher.names()

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            regressions = await check_repos.performance_regressions.list_all(organization_id)
            recommendations = await check_repos.optimization_recommendations.list_all(
                organization_id
            )
        assert len(regressions) == 1
        assert regressions[0].severity == "critical"
        assert len(recommendations) == 1

    async def test_detects_improvement_without_regression_row(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id,
                name="improve-suite",
                benchmark_type=BenchmarkType.DATABASE,
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
        run = await repos.benchmark_runs.create(
            BenchmarkRun(organization_id=organization_id, benchmark_suite_id=suite.id)
        )
        result = BenchmarkResult(
            organization_id=organization_id,
            benchmark_run_id=run.id,
            metric_name="latency_ms",
            value=70.0,
        )
        result.created_at = hours_ago(0.1)
        await repos.benchmark_results.create(result)
        await db_session.commit()

        worker = RegressionSweepWorker(
            db_session_factory,
            publish=publisher,  # type: ignore[arg-type]
            notifier=notifier,  # type: ignore[arg-type]
            warning_threshold_percent=10.0,
            critical_threshold_percent=25.0,
            improvement_threshold_percent=10.0,
            lookback_seconds=3600,
        )
        detected = await worker.tick()
        assert detected == 0
        assert "PerformanceImproved" in publisher.names()
        assert "RegressionDetected" not in publisher.names()

    async def test_no_detection_outside_lookback_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id,
                name="stale-suite",
                benchmark_type=BenchmarkType.DATABASE,
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
        run = await repos.benchmark_runs.create(
            BenchmarkRun(organization_id=organization_id, benchmark_suite_id=suite.id)
        )
        result = BenchmarkResult(
            organization_id=organization_id,
            benchmark_run_id=run.id,
            metric_name="latency_ms",
            value=150.0,
        )
        result.created_at = hours_ago(5)
        await repos.benchmark_results.create(result)
        await db_session.commit()

        worker = RegressionSweepWorker(
            db_session_factory,
            publish=publisher,  # type: ignore[arg-type]
            notifier=notifier,  # type: ignore[arg-type]
            warning_threshold_percent=10.0,
            critical_threshold_percent=25.0,
            improvement_threshold_percent=10.0,
            lookback_seconds=3600,
        )
        detected = await worker.tick()
        assert detected == 0
        assert publisher.events == []


class TestSloComplianceSweepWorkerBehaviour:
    async def test_notifies_once_for_newly_violated_slo(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        result = SloResult(
            organization_id=organization_id,
            slo_name="api-availability",
            sli_type=SliType.AVAILABILITY,
            target_value=99.9,
            actual_value=99.0,
            is_compliant=False,
            evaluated_at=hours_ago(0.1),
        )
        await repos.slo_results.create(result)
        await db_session.commit()

        worker = SloComplianceSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 1
        assert "SLOViolated" in publisher.names()
        assert any(call[0] == "notify_slo_violation" for call in notifier.calls)

    async def test_no_notification_when_compliant(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        result = SloResult(
            organization_id=organization_id,
            slo_name="api-availability-2",
            sli_type=SliType.AVAILABILITY,
            target_value=99.9,
            actual_value=99.95,
            is_compliant=True,
            evaluated_at=hours_ago(0.1),
        )
        await repos.slo_results.create(result)
        await db_session.commit()

        worker = SloComplianceSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []

    async def test_no_notification_outside_lookback_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        result = SloResult(
            organization_id=organization_id,
            slo_name="api-availability-3",
            sli_type=SliType.AVAILABILITY,
            target_value=99.9,
            actual_value=90.0,
            is_compliant=False,
            evaluated_at=hours_ago(5),
        )
        await repos.slo_results.create(result)
        await db_session.commit()

        worker = SloComplianceSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 0


class TestCapacityThresholdSweepWorkerBehaviour:
    async def test_notifies_on_breach_and_creates_scaling_recommendation(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        model = await repos.capacity_models.create(
            CapacityModel(
                organization_id=organization_id,
                name="db-storage",
                resource_type=ResourceType.STORAGE,
                growth_rate_percent=10.0,
            )
        )
        forecast = CapacityForecast(
            organization_id=organization_id,
            capacity_model_id=model.id,
            forecast_date=utcnow(),
            projected_value=95.0,
            threshold_value=90.0,
        )
        forecast.created_at = hours_ago(0.1)
        await repos.capacity_forecasts.create(forecast)
        await db_session.commit()

        worker = CapacityThresholdSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 1
        assert "CapacityThresholdReached" in publisher.names()
        assert any(call[0] == "notify_capacity_warning" for call in notifier.calls)

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            recommendations = await check_repos.optimization_recommendations.list_all(
                organization_id
            )
        assert len(recommendations) == 1
        assert recommendations[0].category == "scaling"

    async def test_no_notification_when_not_breached(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        model = await repos.capacity_models.create(
            CapacityModel(
                organization_id=organization_id,
                name="db-storage-2",
                resource_type=ResourceType.STORAGE,
                growth_rate_percent=10.0,
            )
        )
        forecast = CapacityForecast(
            organization_id=organization_id,
            capacity_model_id=model.id,
            forecast_date=utcnow(),
            projected_value=50.0,
            threshold_value=90.0,
        )
        forecast.created_at = hours_ago(0.1)
        await repos.capacity_forecasts.create(forecast)
        await db_session.commit()

        worker = CapacityThresholdSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []


class TestStatisticsRollupWorkerBehaviour:
    async def test_rolls_up_completed_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id,
                name="rollup-suite",
                benchmark_type=BenchmarkType.API,
            )
        )
        run = BenchmarkRun(
            organization_id=organization_id,
            benchmark_suite_id=suite.id,
            status=BenchmarkRunStatus.SUCCEEDED,
            started_at=hours_ago(2),
        )
        await repos.benchmark_runs.create(run)

        slo_result = SloResult(
            organization_id=organization_id,
            slo_name="rollup-slo",
            sli_type=SliType.LATENCY,
            target_value=100.0,
            actual_value=90.0,
            is_compliant=True,
            evaluated_at=hours_ago(2),
        )
        await repos.slo_results.create(slo_result)
        await db_session.commit()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        rolled = await worker.tick()
        assert rolled >= 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            rows = await check_repos.statistics.list_range(organization_id, since=hours_ago(4))
        assert len(rows) == 1
        assert rows[0].benchmark_run_count == 1


class TestNotifierAndPublisherSanity:
    def test_notifier_and_publisher_importable(self) -> None:
        assert BenchmarkNotifier is not None
        assert EventPublisher is not None
