"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.backup import BackupJob, BackupSchedule, BackupTarget
from app.models.enums import (
    BackupJobStatus,
    BackupTargetKind,
    BackupType,
    ReplicationMode,
    ReplicationScope,
    ScheduleFrequency,
)
from app.models.recovery import ReplicationJob
from app.workers.backup_scheduler import BackupSchedulerWorker
from app.workers.replication_monitor import ReplicationMonitorWorker
from app.workers.retention_sweep import RetentionSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.verification_sweep import VerificationSweepWorker


def now() -> datetime:
    return datetime.now(UTC)


class TestBackupSchedulerWorker:
    async def test_tick_starts_due_schedule_and_advances_next_run(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        schedule = await repos.schedules.create(
            BackupSchedule(
                organization_id=organization_id,
                target_id=target.id,
                backup_type=BackupType.FULL,
                frequency=ScheduleFrequency.DAILY,
                is_enabled=True,
                next_run_at=now() - timedelta(hours=1),
            )
        )

        async def _noop_publish(event: object) -> None:
            pass

        worker = BackupSchedulerWorker(db_session_factory, publish_event=_noop_publish)
        started = await worker.tick()
        assert started == 1

        await db_session.refresh(schedule)
        assert schedule.last_run_at is not None
        assert schedule.next_run_at > now()

    async def test_tick_no_due_schedules_starts_nothing(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        await repos.schedules.create(
            BackupSchedule(
                organization_id=organization_id,
                target_id=target.id,
                backup_type=BackupType.FULL,
                frequency=ScheduleFrequency.DAILY,
                is_enabled=True,
                next_run_at=now() + timedelta(hours=1),
            )
        )

        async def _noop_publish(event: object) -> None:
            pass

        worker = BackupSchedulerWorker(db_session_factory, publish_event=_noop_publish)
        started = await worker.tick()
        assert started == 0

    async def test_tick_no_organizations_no_start(self, db_session_factory) -> None:
        async def _noop_publish(event: object) -> None:
            pass

        worker = BackupSchedulerWorker(db_session_factory, publish_event=_noop_publish)
        assert await worker.tick() == 0


class TestRetentionSweepWorker:
    async def test_tick_applies_enabled_policy_and_records_sweep(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        from app.models.backup import BackupArchive, BackupRetention

        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id, target_id=target.id, backup_type=BackupType.FULL
            )
        )
        await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=now() - timedelta(days=100),
            )
        )
        policy = await repos.retention.create(
            BackupRetention(
                organization_id=organization_id,
                retention_days=90,
                archive_after_days=30,
                is_enabled=True,
            )
        )

        worker = RetentionSweepWorker(db_session_factory)
        deleted = await worker.tick()
        assert deleted == 1

        await db_session.refresh(policy)
        assert policy.last_purged_count == 1

    async def test_tick_no_policies_no_deletions(self, db_session_factory) -> None:
        worker = RetentionSweepWorker(db_session_factory)
        assert await worker.tick() == 0


class TestVerificationSweepWorker:
    async def test_tick_queues_never_verified_job(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        await repos.jobs.create(
            BackupJob(
                organization_id=organization_id,
                target_id=target.id,
                backup_type=BackupType.FULL,
                status=BackupJobStatus.COMPLETED,
                checksum="abc123",
            )
        )

        worker = VerificationSweepWorker(db_session_factory, max_age_days=7, sample_fraction=0.0)
        queued = await worker.tick()
        assert queued == 1

    async def test_tick_skips_jobs_without_checksum(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        await repos.jobs.create(
            BackupJob(
                organization_id=organization_id,
                target_id=target.id,
                backup_type=BackupType.FULL,
                status=BackupJobStatus.COMPLETED,
                checksum=None,
            )
        )

        worker = VerificationSweepWorker(db_session_factory, max_age_days=7, sample_fraction=0.0)
        queued = await worker.tick()
        assert queued == 0

    async def test_tick_no_organizations_no_queue(self, db_session_factory) -> None:
        worker = VerificationSweepWorker(db_session_factory, max_age_days=7, sample_fraction=0.0)
        assert await worker.tick() == 0


class TestReplicationMonitorWorker:
    async def test_tick_reclassifies_status_from_lag(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        job = await repos.replication_jobs.create(
            ReplicationJob(
                organization_id=organization_id,
                target_id=target.id,
                mode=ReplicationMode.ASYNCHRONOUS,
                scope=ReplicationScope.LOCAL,
                destination_ref="dest-1",
                lag_seconds=5000.0,
            )
        )

        worker = ReplicationMonitorWorker(
            db_session_factory, warning_threshold_seconds=300.0, critical_threshold_seconds=1800.0
        )
        checked = await worker.tick()
        assert checked == 1

        await db_session.refresh(job)
        assert job.status == "stalled"

    async def test_tick_no_jobs_checks_nothing(self, db_session_factory) -> None:
        worker = ReplicationMonitorWorker(
            db_session_factory, warning_threshold_seconds=300.0, critical_threshold_seconds=1800.0
        )
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id, name="t1", target_kind=BackupTargetKind.POSTGRESQL
            )
        )
        window_end = now().replace(minute=0, second=0, microsecond=0)
        completion_time = window_end - timedelta(minutes=30)
        await repos.jobs.create(
            BackupJob(
                organization_id=organization_id,
                target_id=target.id,
                backup_type=BackupType.FULL,
                status=BackupJobStatus.COMPLETED,
                completed_at=completion_time,
                size_bytes=1024,
            )
        )

        worker = StatisticsRollupWorker(db_session_factory, window_hours=1)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
