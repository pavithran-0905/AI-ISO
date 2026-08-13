"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.backup import (
    BackupArchive,
    BackupJob,
    BackupRetention,
    BackupSchedule,
    BackupSnapshot,
    BackupTarget,
    BackupVerification,
)
from app.models.enums import (
    AuditAction,
    BackupJobStatus,
    BackupTargetKind,
    BackupType,
    DrPlanStatus,
    DrTestKind,
    DrTestStatus,
    FailoverKind,
    FailoverStatus,
    ReplicationMode,
    ReplicationScope,
    ReportKind,
    ReportStatus,
    RestoreJobStatus,
    RestoreKind,
    RestorePointKind,
    ScheduleFrequency,
    SnapshotKind,
    VerificationKind,
)
from app.models.operations import BackupAudit, BackupReport, BackupStatistic
from app.models.recovery import (
    DrPlan,
    DrTest,
    FailoverEvent,
    RecoveryReport,
    ReplicationJob,
    RestoreJob,
    RestorePoint,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _target(
    organization_id: UUID, *, name: str = "primary-db", is_enabled: bool = True
) -> BackupTarget:
    return BackupTarget(
        organization_id=organization_id,
        name=name,
        target_kind=BackupTargetKind.POSTGRESQL,
        is_enabled=is_enabled,
    )


class TestBackupTargetRepository:
    async def test_find_by_name(self, repos, organization_id: UUID) -> None:
        created = await repos.targets.create(_target(organization_id, name="find-me"))
        found = await repos.targets.find_by_name(organization_id, "find-me")
        assert found is not None
        assert found.id == created.id

    async def test_find_by_name_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.targets.find_by_name(organization_id, "ghost") is None

    async def test_require_in_org_found(self, repos, organization_id: UUID) -> None:
        created = await repos.targets.create(_target(organization_id))
        found = await repos.targets.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.targets.require_in_org(organization_id, uuid4())

    async def test_require_in_org_wrong_org_raises(self, repos, organization_id: UUID) -> None:
        created = await repos.targets.create(_target(organization_id))
        with pytest.raises(NotFoundError):
            await repos.targets.require_in_org(uuid4(), created.id)

    async def test_list_enabled_excludes_disabled(self, repos, organization_id: UUID) -> None:
        await repos.targets.create(_target(organization_id, name="on", is_enabled=True))
        await repos.targets.create(_target(organization_id, name="off", is_enabled=False))
        found = await repos.targets.list_enabled(organization_id)
        assert {t.name for t in found} == {"on"}

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        await repos.targets.create(_target(organization_id))
        org_ids = await repos.targets.list_organization_ids()
        assert organization_id in org_ids


class TestBackupScheduleRepository:
    async def _schedule(
        self, repos, target_id: UUID, organization_id: UUID, **kwargs: object
    ) -> BackupSchedule:
        defaults = {
            "organization_id": organization_id,
            "target_id": target_id,
            "backup_type": BackupType.FULL,
            "frequency": ScheduleFrequency.DAILY,
            "is_enabled": True,
        }
        defaults.update(kwargs)
        return await repos.schedules.create(BackupSchedule(**defaults))

    async def test_list_for_target(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._schedule(repos, target.id, organization_id)
        found = await repos.schedules.list_for_target(target.id)
        assert len(found) == 1

    async def test_list_due(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._schedule(
            repos, target.id, organization_id, next_run_at=NOW - timedelta(hours=1)
        )
        await self._schedule(
            repos, target.id, organization_id, next_run_at=NOW + timedelta(hours=1)
        )
        due = await repos.schedules.list_due(organization_id, now=NOW)
        assert len(due) == 1

    async def test_list_due_excludes_disabled(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._schedule(
            repos,
            target.id,
            organization_id,
            next_run_at=NOW - timedelta(hours=1),
            is_enabled=False,
        )
        due = await repos.schedules.list_due(organization_id, now=NOW)
        assert due == []

    async def test_list_due_excludes_null_next_run(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._schedule(repos, target.id, organization_id, next_run_at=None)
        due = await repos.schedules.list_due(organization_id, now=NOW)
        assert due == []

    async def test_list_enabled(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._schedule(repos, target.id, organization_id, is_enabled=True)
        await self._schedule(repos, target.id, organization_id, is_enabled=False)
        found = await repos.schedules.list_enabled(organization_id)
        assert len(found) == 1


class TestBackupJobRepository:
    async def _job(
        self, repos, target_id: UUID, organization_id: UUID, **kwargs: object
    ) -> BackupJob:
        defaults = {
            "organization_id": organization_id,
            "target_id": target_id,
            "backup_type": BackupType.FULL,
            "status": BackupJobStatus.COMPLETED,
        }
        defaults.update(kwargs)
        return await repos.jobs.create(BackupJob(**defaults))

    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        job = await self._job(repos, target.id, organization_id)
        found = await repos.jobs.require_in_org(organization_id, job.id)
        assert found.id == job.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.jobs.require_in_org(organization_id, uuid4())

    async def test_list_recent_filters_by_target_and_status(
        self, repos, organization_id: UUID
    ) -> None:
        target_a = await repos.targets.create(_target(organization_id, name="a"))
        target_b = await repos.targets.create(_target(organization_id, name="b"))
        await self._job(repos, target_a.id, organization_id, status=BackupJobStatus.COMPLETED)
        await self._job(repos, target_a.id, organization_id, status=BackupJobStatus.FAILED)
        await self._job(repos, target_b.id, organization_id, status=BackupJobStatus.COMPLETED)

        by_target = await repos.jobs.list_recent(organization_id, target_id=target_a.id)
        assert len(by_target) == 2

        by_status = await repos.jobs.list_recent(organization_id, status=BackupJobStatus.FAILED)
        assert len(by_status) == 1

    async def test_list_recent_respects_limit(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        for _ in range(3):
            await self._job(repos, target.id, organization_id)
        found = await repos.jobs.list_recent(organization_id, limit=2)
        assert len(found) == 2

    async def test_list_chain_for_target(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        full = await self._job(repos, target.id, organization_id, backup_type=BackupType.FULL)
        await self._job(
            repos,
            target.id,
            organization_id,
            backup_type=BackupType.INCREMENTAL,
            parent_job_id=full.id,
        )
        chain = await repos.jobs.list_chain_for_target(target.id)
        assert len(chain) == 2

    async def test_list_running(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._job(repos, target.id, organization_id, status=BackupJobStatus.RUNNING)
        await self._job(repos, target.id, organization_id, status=BackupJobStatus.PENDING)
        await self._job(repos, target.id, organization_id, status=BackupJobStatus.COMPLETED)
        running = await repos.jobs.list_running(organization_id)
        assert len(running) == 2


class TestBackupSnapshotRepository:
    async def _snapshot(
        self, repos, target_id: UUID, organization_id: UUID, **kwargs: object
    ) -> BackupSnapshot:
        defaults = {
            "organization_id": organization_id,
            "target_id": target_id,
            "snapshot_kind": SnapshotKind.VOLUME,
            "created_at_source": NOW,
        }
        defaults.update(kwargs)
        return await repos.snapshots.create(BackupSnapshot(**defaults))

    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._snapshot(repos, target.id, organization_id)
        found = await repos.snapshots.list_recent(organization_id, target_id=target.id)
        assert len(found) == 1

    async def test_list_for_target(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._snapshot(repos, target.id, organization_id)
        found = await repos.snapshots.list_for_target(target.id)
        assert len(found) == 1

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await self._snapshot(repos, target.id, organization_id)
        org_ids = await repos.snapshots.list_organization_ids()
        assert organization_id in org_ids


class TestBackupArchiveRepository:
    async def _archive(
        self, repos, job_id: UUID, organization_id: UUID, **kwargs: object
    ) -> BackupArchive:
        defaults = {
            "organization_id": organization_id,
            "job_id": job_id,
            "storage_ref": "s3://bucket/key",
            "archived_at": NOW,
        }
        defaults.update(kwargs)
        return await repos.archives.create(BackupArchive(**defaults))

    async def test_list_for_organization(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id,
                target_id=target.id,
                backup_type=BackupType.FULL,
            )
        )
        await self._archive(repos, job.id, organization_id)
        found = await repos.archives.list_for_organization(organization_id)
        assert len(found) == 1

    async def test_list_for_target_kind_joins_through_job_and_target(
        self, repos, organization_id: UUID
    ) -> None:
        pg_target = await repos.targets.create(_target(organization_id, name="pg"))
        redis_target = await repos.targets.create(
            BackupTarget(
                organization_id=organization_id,
                name="redis",
                target_kind=BackupTargetKind.REDIS,
            )
        )
        pg_job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id, target_id=pg_target.id, backup_type=BackupType.FULL
            )
        )
        redis_job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id,
                target_id=redis_target.id,
                backup_type=BackupType.FULL,
            )
        )
        await self._archive(repos, pg_job.id, organization_id)
        await self._archive(repos, redis_job.id, organization_id)

        pg_archives = await repos.archives.list_for_target_kind(
            organization_id, BackupTargetKind.POSTGRESQL
        )
        assert len(pg_archives) == 1

    async def test_list_for_target_kind_none_returns_all(
        self, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(_target(organization_id))
        job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id, target_id=target.id, backup_type=BackupType.FULL
            )
        )
        await self._archive(repos, job.id, organization_id)
        found = await repos.archives.list_for_target_kind(organization_id, None)
        assert len(found) == 1

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id, target_id=target.id, backup_type=BackupType.FULL
            )
        )
        await self._archive(repos, job.id, organization_id)
        org_ids = await repos.archives.list_organization_ids()
        assert organization_id in org_ids


class TestBackupRetentionRepository:
    async def _policy(self, repos, organization_id: UUID, **kwargs: object) -> BackupRetention:
        defaults = {"organization_id": organization_id, "environment": "production"}
        defaults.update(kwargs)
        return await repos.retention.create(BackupRetention(**defaults))

    async def test_list_enabled(self, repos, organization_id: UUID) -> None:
        await self._policy(repos, organization_id, is_enabled=True)
        await self._policy(repos, organization_id, is_enabled=False, environment="staging")
        found = await repos.retention.list_enabled(organization_id)
        assert len(found) == 1

    async def test_find_for_scope(self, repos, organization_id: UUID) -> None:
        await self._policy(
            repos,
            organization_id,
            target_kind=BackupTargetKind.POSTGRESQL,
            environment="production",
        )
        found = await repos.retention.find_for_scope(
            organization_id, BackupTargetKind.POSTGRESQL, "production"
        )
        assert found is not None

    async def test_find_for_scope_missing_returns_none(self, repos, organization_id: UUID) -> None:
        found = await repos.retention.find_for_scope(organization_id, None, "production")
        assert found is None

    async def test_list_organization_ids_only_enabled(self, repos, organization_id: UUID) -> None:
        await self._policy(repos, organization_id, is_enabled=True)
        org_ids = await repos.retention.list_organization_ids()
        assert organization_id in org_ids


class TestBackupVerificationRepository:
    async def _verification(
        self, repos, job_id: UUID, organization_id: UUID, **kwargs: object
    ) -> BackupVerification:
        defaults = {
            "organization_id": organization_id,
            "job_id": job_id,
            "verification_kind": VerificationKind.CHECKSUM,
        }
        defaults.update(kwargs)
        return await repos.verifications.create(BackupVerification(**defaults))

    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id, target_id=target.id, backup_type=BackupType.FULL
            )
        )
        await self._verification(repos, job.id, organization_id)
        found = await repos.verifications.list_recent(organization_id, job_id=job.id)
        assert len(found) == 1

    async def test_latest_for_job(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        job = await repos.jobs.create(
            BackupJob(
                organization_id=organization_id, target_id=target.id, backup_type=BackupType.FULL
            )
        )
        await self._verification(
            repos, job.id, organization_id, verified_at=NOW - timedelta(days=1)
        )
        await self._verification(repos, job.id, organization_id, verified_at=NOW)
        latest = await repos.verifications.latest_for_job(job.id)
        assert latest is not None
        assert latest.verified_at == NOW

    async def test_latest_for_job_none_when_absent(self, repos, organization_id: UUID) -> None:
        assert await repos.verifications.latest_for_job(uuid4()) is None


class TestRestorePointRepository:
    async def test_list_for_target(self, repos, organization_id: UUID) -> None:
        target = await repos.targets.create(_target(organization_id))
        await repos.restore_points.create(
            RestorePoint(
                organization_id=organization_id,
                target_id=target.id,
                point_kind=RestorePointKind.BACKUP_COMPLETION,
                available_at=NOW,
            )
        )
        found = await repos.restore_points.list_for_target(target.id)
        assert len(found) == 1


class TestRestoreJobRepository:
    async def _restore_job(self, repos, organization_id: UUID, **kwargs: object) -> RestoreJob:
        defaults = {"organization_id": organization_id, "restore_kind": RestoreKind.FULL}
        defaults.update(kwargs)
        return await repos.restore_jobs.create(RestoreJob(**defaults))

    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        job = await self._restore_job(repos, organization_id)
        found = await repos.restore_jobs.require_in_org(organization_id, job.id)
        assert found.id == job.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.restore_jobs.require_in_org(organization_id, uuid4())

    async def test_list_recent_filters_by_status(self, repos, organization_id: UUID) -> None:
        await self._restore_job(repos, organization_id, status=RestoreJobStatus.COMPLETED)
        await self._restore_job(repos, organization_id, status=RestoreJobStatus.FAILED)
        found = await repos.restore_jobs.list_recent(
            organization_id, status=RestoreJobStatus.FAILED
        )
        assert len(found) == 1


class TestReplicationJobRepository:
    async def test_list_for_organization_and_organization_ids(
        self, repos, organization_id: UUID
    ) -> None:
        target = await repos.targets.create(_target(organization_id))
        await repos.replication_jobs.create(
            ReplicationJob(
                organization_id=organization_id,
                target_id=target.id,
                mode=ReplicationMode.ASYNCHRONOUS,
                scope=ReplicationScope.LOCAL,
                destination_ref="dest-1",
            )
        )
        found = await repos.replication_jobs.list_for_organization(organization_id)
        assert len(found) == 1
        org_ids = await repos.replication_jobs.list_organization_ids()
        assert organization_id in org_ids


class TestDrPlanRepository:
    async def _plan(self, repos, organization_id: UUID, **kwargs: object) -> DrPlan:
        defaults = {"organization_id": organization_id, "name": "plan-1"}
        defaults.update(kwargs)
        return await repos.dr_plans.create(DrPlan(**defaults))

    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        plan = await self._plan(repos, organization_id)
        found = await repos.dr_plans.require_in_org(organization_id, plan.id)
        assert found.id == plan.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.dr_plans.require_in_org(organization_id, uuid4())

    async def test_list_active(self, repos, organization_id: UUID) -> None:
        await self._plan(repos, organization_id, status=DrPlanStatus.ACTIVE, is_active=True)
        await self._plan(
            repos, organization_id, status=DrPlanStatus.DRAFT, is_active=True, name="draft"
        )
        found = await repos.dr_plans.list_active(organization_id)
        assert len(found) == 1

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        await self._plan(repos, organization_id, is_active=True)
        org_ids = await repos.dr_plans.list_organization_ids()
        assert organization_id in org_ids


class TestDrTestRepository:
    async def _plan_and_test(
        self, repos, organization_id: UUID, **kwargs: object
    ) -> tuple[DrPlan, DrTest]:
        plan = await repos.dr_plans.create(DrPlan(organization_id=organization_id, name="plan-1"))
        defaults = {
            "organization_id": organization_id,
            "dr_plan_id": plan.id,
            "test_kind": DrTestKind.SIMULATION,
        }
        defaults.update(kwargs)
        test = await repos.dr_tests.create(DrTest(**defaults))
        return plan, test

    async def test_list_for_plan(self, repos, organization_id: UUID) -> None:
        plan, _test = await self._plan_and_test(repos, organization_id)
        found = await repos.dr_tests.list_for_plan(plan.id)
        assert len(found) == 1

    async def test_list_due(self, repos, organization_id: UUID) -> None:
        await self._plan_and_test(
            repos,
            organization_id,
            status=DrTestStatus.SCHEDULED,
            scheduled_at=NOW - timedelta(hours=1),
        )
        due = await repos.dr_tests.list_due(organization_id, now=NOW)
        assert len(due) == 1

    async def test_list_due_excludes_not_scheduled_status(
        self, repos, organization_id: UUID
    ) -> None:
        await self._plan_and_test(
            repos,
            organization_id,
            status=DrTestStatus.PASSED,
            scheduled_at=NOW - timedelta(hours=1),
        )
        due = await repos.dr_tests.list_due(organization_id, now=NOW)
        assert due == []


class TestFailoverEventRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.failover_events.create(
            FailoverEvent(
                organization_id=organization_id,
                failover_kind=FailoverKind.MANUAL,
                status=FailoverStatus.INITIATED,
                initiated_at=NOW,
            )
        )
        found = await repos.failover_events.list_recent(organization_id)
        assert len(found) == 1


class TestRecoveryReportRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.recovery_reports.create(
            RecoveryReport(organization_id=organization_id, generated_at=NOW)
        )
        found = await repos.recovery_reports.list_recent(organization_id)
        assert len(found) == 1


class TestBackupStatisticRepository:
    async def test_find_window(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            BackupStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(
            organization_id, window_start=NOW, window_end=NOW + timedelta(hours=1)
        )
        assert found is not None

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        found = await repos.statistics.find_window(
            organization_id, window_start=NOW, window_end=NOW + timedelta(hours=1)
        )
        assert found is None

    async def test_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            BackupStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.list_range(
            organization_id, start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=2)
        )
        assert len(found) == 1


class TestBackupReportRepository:
    async def _report(self, repos, organization_id: UUID, **kwargs: object) -> BackupReport:
        defaults = {
            "organization_id": organization_id,
            "kind": ReportKind.BACKUP,
            "title": "Report",
        }
        defaults.update(kwargs)
        return await repos.reports.create(BackupReport(**defaults))

    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        report = await self._report(repos, organization_id)
        found = await repos.reports.require_in_org(organization_id, report.id)
        assert found.id == report.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.reports.require_in_org(organization_id, uuid4())

    async def test_list_recent_filters_by_status(self, repos, organization_id: UUID) -> None:
        await self._report(repos, organization_id, status=ReportStatus.COMPLETED)
        await self._report(repos, organization_id, status=ReportStatus.PENDING)
        found = await repos.reports.list_recent(organization_id, status=ReportStatus.PENDING)
        assert len(found) == 1


class TestBackupAuditRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            BackupAudit(
                organization_id=organization_id,
                action=AuditAction.BACKUP_EXECUTED,
                entity_type="backup_job",
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            BackupAudit(
                organization_id=organization_id,
                action=AuditAction.BACKUP_EXECUTED,
                entity_type="backup_job",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
