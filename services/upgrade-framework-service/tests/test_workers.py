"""Integration tests for every worker's ``tick()``, against real
PostgreSQL, exercised directly rather than through the scheduler."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import (
    MigrationType,
    ReleaseChannelType,
    UpgradeJobStatus,
    UpgradeStrategy,
    UpgradeTargetType,
    VerificationCheckType,
)
from app.models.migrations import MigrationHistory
from app.models.releases import ReleaseChannel, ReleaseVersion
from app.models.upgrade import UpgradeJob, UpgradePlan
from app.models.verification import VerificationResult
from app.services.bundle import build_repositories
from app.workers.health_gate_enforcement import HealthGateEnforcementWorker
from app.workers.migration_timeout_sweep import MigrationTimeoutSweepWorker
from app.workers.release_adoption_sweep import ReleaseAdoptionSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.upgrade_job_timeout_sweep import UpgradeJobTimeoutSweepWorker
from tests.conftest import RecordingNotifier, hours_ago, utcnow


async def _make_plan(
    db_session: AsyncSession, organization_id: uuid.UUID, name: str = "p1"
) -> UpgradePlan:
    repos = build_repositories(db_session)
    return await repos.plans.create(
        UpgradePlan(
            organization_id=organization_id,
            name=name,
            target_type=UpgradeTargetType.PLATFORM_SERVICE,
            strategy=UpgradeStrategy.ROLLING,
            from_version="1.0.0",
            to_version="1.1.0",
        )
    )


class TestUpgradeJobTimeoutSweepWorker:
    async def test_fails_only_stuck_jobs(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        plan = await _make_plan(db_session, organization_id)
        stuck = await repos.jobs.create(
            UpgradeJob(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                status=UpgradeJobStatus.RUNNING,
                started_at=hours_ago(10),
            )
        )
        fresh = await repos.jobs.create(
            UpgradeJob(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                status=UpgradeJobStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = UpgradeJobTimeoutSweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=4  # type: ignore[arg-type]
        )
        failed = await worker.tick()
        assert failed >= 1

        await db_session.refresh(stuck)
        await db_session.refresh(fresh)
        assert stuck.status == "failed"
        assert fresh.status == "running"
        assert any(call[0] == "notify_upgrade_failed" for call in notifier.calls)


class TestMigrationTimeoutSweepWorker:
    async def test_fails_only_stuck_migrations(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        plan = await _make_plan(db_session, organization_id, name="p2")
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        stuck = await repos.migration_history.create(
            MigrationHistory(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                migration_type=MigrationType.DATABASE_SCHEMA,
                status=UpgradeJobStatus.RUNNING,
                started_at=hours_ago(5),
            )
        )
        fresh = await repos.migration_history.create(
            MigrationHistory(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                migration_type=MigrationType.PLUGIN,
                status=UpgradeJobStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = MigrationTimeoutSweepWorker(db_session_factory, notifier=notifier, max_age_hours=2)  # type: ignore[arg-type]
        failed = await worker.tick()
        assert failed >= 1

        await db_session.refresh(stuck)
        await db_session.refresh(fresh)
        assert stuck.status == "failed"
        assert fresh.status == "running"


class TestReleaseAdoptionSweepWorker:
    async def test_notifies_when_newer_version_recently_released(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        channel = await repos.channels.create(
            ReleaseChannel(
                organization_id=organization_id,
                name="stable",
                channel_type=ReleaseChannelType.STABLE,
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="1.0.0",
                released_at=hours_ago(48),
                is_current=True,
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="1.1.0",
                released_at=hours_ago(0.1),
            )
        )
        await db_session.flush()

        worker = ReleaseAdoptionSweepWorker(
            db_session_factory, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 1
        assert ("notify_upgrade_available", {"version": "1.1.0"}) in notifier.calls

    async def test_does_not_notify_once_outside_lookback_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        channel = await repos.channels.create(
            ReleaseChannel(
                organization_id=organization_id,
                name="stable2",
                channel_type=ReleaseChannelType.STABLE,
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="1.0.0",
                released_at=hours_ago(48),
                is_current=True,
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="1.1.0",
                released_at=hours_ago(10),
            )
        )
        await db_session.flush()

        worker = ReleaseAdoptionSweepWorker(
            db_session_factory, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []


class TestHealthGateEnforcementWorker:
    async def test_pauses_only_jobs_with_failed_verification(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        plan = await _make_plan(db_session, organization_id, name="p3")
        unhealthy_job = await repos.jobs.create(
            UpgradeJob(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                status=UpgradeJobStatus.RUNNING,
            )
        )
        healthy_job = await repos.jobs.create(
            UpgradeJob(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                status=UpgradeJobStatus.RUNNING,
            )
        )
        await repos.verification_results.create(
            VerificationResult(
                organization_id=organization_id,
                upgrade_job_id=unhealthy_job.id,
                check_type=VerificationCheckType.HEALTH,
                status="failed",
                verified_at=utcnow(),
            )
        )
        await repos.verification_results.create(
            VerificationResult(
                organization_id=organization_id,
                upgrade_job_id=healthy_job.id,
                check_type=VerificationCheckType.HEALTH,
                status="passed",
                verified_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = HealthGateEnforcementWorker(db_session_factory, notifier=notifier)  # type: ignore[arg-type]
        paused = await worker.tick()
        assert paused == 1

        await db_session.refresh(unhealthy_job)
        await db_session.refresh(healthy_job)
        assert unhealthy_job.status == "failed"
        assert healthy_job.status == "running"
        assert any(call[0] == "notify_upgrade_failed" for call in notifier.calls)

    async def test_run_job_entry_point_matches_scheduler_signature(
        self, db_session_factory: async_sessionmaker[AsyncSession], notifier: RecordingNotifier
    ) -> None:
        worker = HealthGateEnforcementWorker(db_session_factory, notifier=notifier)  # type: ignore[arg-type]
        await worker.run_job(object())


class TestStatisticsRollupWorker:
    async def test_rolls_up_and_is_idempotent(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        repos = build_repositories(db_session)
        plan = await _make_plan(db_session, organization_id, name="p4")
        await repos.jobs.create(
            UpgradeJob(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                status=UpgradeJobStatus.SUCCEEDED,
                started_at=hours_ago(1),
                completed_at=hours_ago(1),
            )
        )
        await db_session.flush()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        first_rolled = await worker.tick()
        assert first_rolled >= 1
        second_rolled = await worker.tick()
        assert second_rolled >= 1

        stats = await repos.statistics.list_range(organization_id, since=hours_ago(72))
        assert len(stats) == 1
        assert stats[0].upgrade_count == 1
        assert stats[0].success_count == 1
