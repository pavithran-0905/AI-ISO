"""Integration tests for every worker, against real PostgreSQL.

See ``test_repositories.py``'s own module docstring for why every
model/enum starting with ``Test`` is imported under an alias here too.
Each worker is exercised by calling its own ``tick()`` directly --
never through the scheduler -- matching every other service's own
worker test shape in this codebase.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import CoverageType
from app.models.enums import TestResultStatus as ResultStatusEnum
from app.models.enums import TestRunStatus as RunStatusEnum
from app.models.enums import TestType as SuiteTypeEnum
from app.models.pipeline import PipelineResult
from app.models.test_definitions import TestCase as CaseModel
from app.models.test_definitions import TestSuite as SuiteModel
from app.models.test_execution import TestResult as ResultModel
from app.models.test_execution import TestRun as RunModel
from app.services.bundle import Repositories, build_repositories
from app.services.notifications import QaNotifier
from app.workers.coverage_drop_sweep import CoverageDropSweepWorker
from app.workers.flaky_test_detection import FlakyTestDetectionWorker
from app.workers.pipeline_timeout_sweep import PipelineTimeoutSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.test_run_timeout_sweep import TestRunTimeoutSweepWorker as RunTimeoutSweepWorker
from tests.conftest import RecordingNotifier, hours_ago, utcnow


async def _make_suite_and_case(
    repos: Repositories, organization_id: uuid.UUID
) -> tuple[SuiteModel, CaseModel]:
    suite = await repos.test_suites.create(
        SuiteModel(
            organization_id=organization_id, name="worker-suite", test_type=SuiteTypeEnum.UNIT
        )
    )
    case = await repos.test_cases.create(
        CaseModel(organization_id=organization_id, test_suite_id=suite.id, name="worker-case")
    )
    return suite, case


class TestRunTimeoutSweepWorkerBehaviour:
    async def test_fails_stuck_run_on_next_tick(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        suite, _case = await _make_suite_and_case(repos, organization_id)
        stuck_run = await repos.test_runs.create(
            RunModel(
                organization_id=organization_id,
                test_suite_id=suite.id,
                status=RunStatusEnum.RUNNING,
                started_at=hours_ago(5),
            )
        )
        fresh_run = await repos.test_runs.create(
            RunModel(
                organization_id=organization_id,
                test_suite_id=suite.id,
                status=RunStatusEnum.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.commit()

        worker = RunTimeoutSweepWorker(db_session_factory, max_age_hours=4)
        failed = await worker.tick()
        assert failed == 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            reread_stuck = await check_repos.test_runs.require_by_id(stuck_run.id)
            reread_fresh = await check_repos.test_runs.require_by_id(fresh_run.id)
        assert reread_stuck.status == "failed"
        assert reread_fresh.status == "running"


class TestPipelineTimeoutSweepWorkerBehaviour:
    async def test_fails_stuck_pipeline_and_notifies(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        stuck_pipeline = await repos.pipeline_results.create(
            PipelineResult(
                organization_id=organization_id,
                name="stuck-pipeline",
                status=RunStatusEnum.RUNNING,
                started_at=hours_ago(5),
            )
        )
        await db_session.commit()

        worker = PipelineTimeoutSweepWorker(db_session_factory, notifier=notifier, max_age_hours=4)  # type: ignore[arg-type]
        failed = await worker.tick()
        assert failed == 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            reread = await check_repos.pipeline_results.require_by_id(stuck_pipeline.id)
        assert reread.status == "failed"
        assert any(call[0] == "notify_pipeline_failed" for call in notifier.calls)


class TestFlakyTestDetectionWorkerBehaviour:
    async def test_notifies_once_for_newly_flaky_case(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        suite, case = await _make_suite_and_case(repos, organization_id)
        run = await repos.test_runs.create(
            RunModel(organization_id=organization_id, test_suite_id=suite.id)
        )
        for status in (ResultStatusEnum.PASSED, ResultStatusEnum.FAILED, ResultStatusEnum.PASSED):
            result = ResultModel(
                organization_id=organization_id,
                test_run_id=run.id,
                test_case_id=case.id,
                status=status,
            )
            result.created_at = hours_ago(0.1)
            await repos.test_results.create(result)
        await db_session.commit()

        worker = FlakyTestDetectionWorker(  # type: ignore[arg-type]
            db_session_factory, notifier=notifier, lookback_seconds=3600
        )

        first_tick = await worker.tick()
        assert first_tick == 1
        assert any(call[0] == "notify_flaky_test_detected" for call in notifier.calls)

        notifier.calls.clear()
        second_tick = await worker.tick()
        assert second_tick == 1

    async def test_does_not_notify_stable_case(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        suite, case = await _make_suite_and_case(repos, organization_id)
        run = await repos.test_runs.create(
            RunModel(organization_id=organization_id, test_suite_id=suite.id)
        )
        for _ in range(3):
            result = ResultModel(
                organization_id=organization_id,
                test_run_id=run.id,
                test_case_id=case.id,
                status=ResultStatusEnum.PASSED,
            )
            result.created_at = hours_ago(0.1)
            await repos.test_results.create(result)
        await db_session.commit()

        worker = FlakyTestDetectionWorker(  # type: ignore[arg-type]
            db_session_factory, notifier=notifier, lookback_seconds=3600
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []

    async def test_does_not_notify_outside_lookback_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        suite, case = await _make_suite_and_case(repos, organization_id)
        run = await repos.test_runs.create(
            RunModel(organization_id=organization_id, test_suite_id=suite.id)
        )
        for status in (ResultStatusEnum.PASSED, ResultStatusEnum.FAILED):
            result = ResultModel(
                organization_id=organization_id,
                test_run_id=run.id,
                test_case_id=case.id,
                status=status,
            )
            result.created_at = hours_ago(5)
            await repos.test_results.create(result)
        await db_session.commit()

        worker = FlakyTestDetectionWorker(  # type: ignore[arg-type]
            db_session_factory, notifier=notifier, lookback_seconds=3600
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []


class TestCoverageDropSweepWorkerBehaviour:
    async def test_notifies_on_newly_detected_drop(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        from app.models.coverage import CoverageReport

        previous = CoverageReport(
            organization_id=organization_id, coverage_type=CoverageType.UNIT, percentage=95.0
        )
        previous.created_at = hours_ago(1)
        await repos.coverage_reports.create(previous)

        current = CoverageReport(
            organization_id=organization_id, coverage_type=CoverageType.UNIT, percentage=88.0
        )
        current.created_at = hours_ago(0.1)
        await repos.coverage_reports.create(current)
        await db_session.commit()

        worker = CoverageDropSweepWorker(
            db_session_factory, notifier=notifier, drop_threshold_percent=2.0, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 1
        assert any(call[0] == "notify_coverage_dropped" for call in notifier.calls)

    async def test_no_notification_for_small_dip(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        from app.models.coverage import CoverageReport

        previous = CoverageReport(
            organization_id=organization_id, coverage_type=CoverageType.INTEGRATION, percentage=95.0
        )
        previous.created_at = hours_ago(1)
        await repos.coverage_reports.create(previous)

        current = CoverageReport(
            organization_id=organization_id, coverage_type=CoverageType.INTEGRATION, percentage=94.5
        )
        current.created_at = hours_ago(0.1)
        await repos.coverage_reports.create(current)
        await db_session.commit()

        worker = CoverageDropSweepWorker(
            db_session_factory, notifier=notifier, drop_threshold_percent=2.0, lookback_seconds=3600  # type: ignore[arg-type]
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
        suite, case = await _make_suite_and_case(repos, organization_id)
        run = RunModel(
            organization_id=organization_id,
            test_suite_id=suite.id,
            status=RunStatusEnum.SUCCEEDED,
            started_at=hours_ago(2),
        )
        run = await repos.test_runs.create(run)

        result = ResultModel(
            organization_id=organization_id,
            test_run_id=run.id,
            test_case_id=case.id,
            status=ResultStatusEnum.PASSED,
        )
        result.created_at = hours_ago(2)
        await repos.test_results.create(result)
        await db_session.commit()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        rolled = await worker.tick()
        assert rolled >= 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            rows = await check_repos.statistics.list_range(organization_id, since=hours_ago(4))
        assert len(rows) == 1


class TestQaNotifierSanity:
    def test_notifier_class_importable(self) -> None:
        assert QaNotifier is not None
