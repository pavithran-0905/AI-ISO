"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.backup.engine import ChainLink
from app.failover.engine import HealthCheckResult
from app.immutability.engine import LockRefusal
from app.models.backup import BackupArchive, BackupJob, BackupTarget
from app.models.enums import (
    AuditAction,
    BackupJobStatus,
    BackupTargetKind,
    BackupType,
    ComplianceStatus,
    DrTestKind,
    FailoverKind,
    FailoverStatus,
    RecoveryPriority,
    ReportFormat,
    ReportKind,
    RestoreJobStatus,
    RestoreKind,
    SnapshotKind,
    VerificationStatus,
)
from app.models.recovery import DrPlan, DrTest, FailoverEvent, RestoreJob, RestorePoint
from app.services.audit import AuditService
from app.services.backup import BackupJobService, BackupScheduleService, BackupTargetService
from app.services.dr import DrPlanService, DrTestService, RecoveryReportService
from app.services.failover import FailoverService
from app.services.immutability import ImmutabilityService
from app.services.replication import ReplicationService
from app.services.reports import ReportService
from app.services.restore import RestoreService
from app.services.retention import RetentionService
from app.services.snapshots import SnapshotService
from app.services.statistics import StatisticsService
from app.services.verification import VerificationService

NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _target(repos, organization_id: UUID, **kwargs: object) -> BackupTarget:
    defaults = {
        "organization_id": organization_id,
        "name": "t1",
        "target_kind": BackupTargetKind.POSTGRESQL,
    }
    defaults.update(kwargs)
    return await repos.targets.create(BackupTarget(**defaults))


async def _job(repos, organization_id: UUID, target_id: UUID, **kwargs: object) -> BackupJob:
    defaults = {
        "organization_id": organization_id,
        "target_id": target_id,
        "backup_type": BackupType.FULL,
        "status": BackupJobStatus.RUNNING,
        "started_at": NOW,
    }
    defaults.update(kwargs)
    return await repos.jobs.create(BackupJob(**defaults))


class TestAuditService:
    async def test_record_creates_entry(self, repos, organization_id: UUID) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="backup_target",
            entity_id=uuid4(),
            occurred_at=NOW,
            summary="test entry",
        )
        assert entry.id is not None
        assert entry.action is AuditAction.ADMINISTRATIVE

    async def test_record_defaults_details_to_empty_dict(
        self, repos, organization_id: UUID
    ) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="backup_target",
            entity_id=None,
            occurred_at=NOW,
        )
        assert entry.details == {}


class TestBackupTargetService:
    async def test_register_target_without_audit(self, repos, organization_id: UUID) -> None:
        service = BackupTargetService(repos.targets)
        target = await service.register_target(
            organization_id,
            name="db-1",
            target_kind=BackupTargetKind.POSTGRESQL,
            environment="production",
            connection_ref=None,
            actor_id="tester",
            now=NOW,
        )
        assert target.name == "db-1"

    async def test_register_target_with_audit_records_entry(
        self, repos, organization_id: UUID
    ) -> None:
        audit = AuditService(repos.audit)
        service = BackupTargetService(repos.targets, audit=audit)
        await service.register_target(
            organization_id,
            name="db-2",
            target_kind=BackupTargetKind.POSTGRESQL,
            environment="production",
            connection_ref="secret-ref",
            actor_id="tester",
            now=NOW,
        )
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 1


class TestBackupScheduleService:
    async def test_create_schedule_computes_next_run(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        service = BackupScheduleService(repos.schedules)
        schedule = await service.create_schedule(
            organization_id,
            target_id=target.id,
            backup_type=BackupType.FULL,
            frequency="daily",
            cron_expression=None,
            retention_days=90,
            actor_id="tester",
            now=NOW,
        )
        assert schedule.next_run_at == NOW

    async def test_create_schedule_custom_cron_has_no_next_run(
        self, repos, organization_id: UUID
    ) -> None:
        target = await _target(repos, organization_id)
        service = BackupScheduleService(repos.schedules)
        schedule = await service.create_schedule(
            organization_id,
            target_id=target.id,
            backup_type=BackupType.FULL,
            frequency="custom_cron",
            cron_expression="0 3 * * *",
            retention_days=90,
            actor_id="tester",
            now=NOW,
        )
        assert schedule.next_run_at is None

    async def test_create_schedule_records_audit(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        audit = AuditService(repos.audit)
        service = BackupScheduleService(repos.schedules, audit=audit)
        await service.create_schedule(
            organization_id,
            target_id=target.id,
            backup_type=BackupType.FULL,
            frequency="daily",
            cron_expression=None,
            retention_days=90,
            actor_id="tester",
            now=NOW,
        )
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 1


class TestBackupJobService:
    async def test_start_job_publishes_event(self, repos, organization_id: UUID, publisher) -> None:
        target = await _target(repos, organization_id)
        service = BackupJobService(repos.jobs, publish=publisher)
        job = await service.start_job(
            organization_id,
            target=target,
            backup_type=BackupType.FULL,
            schedule_id=None,
            parent_job_id=None,
            now=NOW,
        )
        assert job.status is BackupJobStatus.RUNNING
        assert publisher.names() == ["BackupStarted"]

    async def test_complete_job_full_backup_no_chain_check(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id, backup_type=BackupType.FULL)
        service = BackupJobService(repos.jobs, publish=publisher)
        completed = await service.complete_job(
            job,
            size_bytes=1024,
            checksum="abc",
            checksum_algorithm="sha256",
            chain=None,
            existing_checksums=[],
            now=NOW,
        )
        assert completed.status is BackupJobStatus.COMPLETED
        assert "BackupCompleted" in publisher.names()

    async def test_complete_job_broken_chain_fails_not_completes(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(
            repos,
            organization_id,
            target.id,
            backup_type=BackupType.INCREMENTAL,
            parent_job_id=None,
        )
        service = BackupJobService(repos.jobs, publish=publisher)
        completed = await service.complete_job(
            job,
            size_bytes=1024,
            checksum="abc",
            checksum_algorithm="sha256",
            chain=[],
            existing_checksums=[],
            now=NOW,
        )
        assert completed.status is BackupJobStatus.FAILED
        assert "BackupFailed" in publisher.names()

    async def test_complete_job_intact_chain_succeeds(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        target = await _target(repos, organization_id)
        full = await _job(
            repos,
            organization_id,
            target.id,
            backup_type=BackupType.FULL,
            status=BackupJobStatus.COMPLETED,
        )
        job = await _job(
            repos,
            organization_id,
            target.id,
            backup_type=BackupType.INCREMENTAL,
            parent_job_id=full.id,
        )
        chain_link = ChainLink(
            job_id=str(full.id),
            backup_type=BackupType.FULL,
            parent_job_id=None,
            status=BackupJobStatus.COMPLETED,
            completed_at=NOW,
        )
        service = BackupJobService(repos.jobs, publish=publisher)
        completed = await service.complete_job(
            job,
            size_bytes=1024,
            checksum="abc",
            checksum_algorithm="sha256",
            chain=[chain_link],
            existing_checksums=[],
            now=NOW,
        )
        assert completed.status is BackupJobStatus.COMPLETED

    async def test_complete_job_marks_duplicate(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id, backup_type=BackupType.FULL)
        service = BackupJobService(repos.jobs, publish=publisher)
        completed = await service.complete_job(
            job,
            size_bytes=1024,
            checksum="abc",
            checksum_algorithm="sha256",
            chain=None,
            existing_checksums=[("other-job", "abc", 1024)],
            now=NOW,
        )
        assert completed.details.get("duplicate_of_job_id") == "other-job"

    async def test_fail_job_publishes_event(self, repos, organization_id: UUID, publisher) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        service = BackupJobService(repos.jobs, publish=publisher)
        failed = await service.fail_job(job, error_message="disk full", now=NOW)
        assert failed.status is BackupJobStatus.FAILED
        assert failed.error_message == "disk full"
        assert "BackupFailed" in publisher.names()


class TestSnapshotService:
    async def test_create_snapshot(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        service = SnapshotService(repos.snapshots)
        snapshot = await service.create_snapshot(
            organization_id,
            target_id=target.id,
            job_id=None,
            snapshot_kind=SnapshotKind.VOLUME,
            storage_ref="ref-1",
            size_bytes=100,
            created_at_source=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        assert snapshot.id is not None

    async def test_sweep_expired_marks_only_expired(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        service = SnapshotService(repos.snapshots)
        await service.create_snapshot(
            organization_id,
            target_id=target.id,
            job_id=None,
            snapshot_kind=SnapshotKind.VOLUME,
            storage_ref="expired-ref",
            size_bytes=100,
            created_at_source=NOW - timedelta(days=40),
            expires_at=NOW - timedelta(days=1),
        )
        await service.create_snapshot(
            organization_id,
            target_id=target.id,
            job_id=None,
            snapshot_kind=SnapshotKind.VOLUME,
            storage_ref="fresh-ref",
            size_bytes=100,
            created_at_source=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        count = await service.sweep_expired(organization_id, now=NOW)
        assert count == 1

    async def test_enforce_target_quota_evicts_oldest(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        service = SnapshotService(repos.snapshots)
        rows = []
        for i in range(3):
            row = await service.create_snapshot(
                organization_id,
                target_id=target.id,
                job_id=None,
                snapshot_kind=SnapshotKind.VOLUME,
                storage_ref=f"ref-{i}",
                size_bytes=100,
                created_at_source=NOW - timedelta(hours=i),
                expires_at=None,
            )
            rows.append(row)
        evicted_count = await service.enforce_target_quota(target.id, rows, max_per_target=2)
        assert evicted_count == 1


class TestRestoreService:
    async def test_select_point(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        await repos.restore_points.create(
            RestorePoint(
                organization_id=organization_id,
                target_id=target.id,
                point_kind="backup_completion",
                available_at=NOW - timedelta(hours=1),
            )
        )
        service = RestoreService(repos.restore_jobs, repos.restore_points)
        selection = await service.select_point(target.id, requested_at=NOW, now=NOW)
        assert selection.is_selected

    async def test_preview_in_place_is_destructive(self, repos) -> None:
        service = RestoreService(repos.restore_jobs, repos.restore_points)
        preview = service.preview(
            restore_kind=RestoreKind.FULL,
            source_ref="archive-1",
            target_ref="target-1",
            source_ref_equals_original=True,
            estimated_size_bytes=1024,
        )
        assert preview.is_destructive

    async def test_start_job_publishes_event(self, repos, organization_id: UUID, publisher) -> None:
        service = RestoreService(repos.restore_jobs, repos.restore_points, publish=publisher)
        job = await service.start_job(
            organization_id,
            source_archive_id=None,
            restore_point_id=None,
            restore_kind=RestoreKind.FULL,
            target_ref="target-1",
            is_preview=False,
            requested_by="tester",
            now=NOW,
        )
        assert job.status is RestoreJobStatus.RUNNING
        assert publisher.names() == ["RestoreStarted"]

    async def test_start_job_preview_status(self, repos, organization_id: UUID, publisher) -> None:
        service = RestoreService(repos.restore_jobs, repos.restore_points, publish=publisher)
        job = await service.start_job(
            organization_id,
            source_archive_id=None,
            restore_point_id=None,
            restore_kind=RestoreKind.FULL,
            target_ref="target-1",
            is_preview=True,
            requested_by="tester",
            now=NOW,
        )
        assert job.status is RestoreJobStatus.PREVIEWING

    async def test_complete_job_validated(self, repos, organization_id: UUID, publisher) -> None:
        service = RestoreService(repos.restore_jobs, repos.restore_points, publish=publisher)
        job = await repos.restore_jobs.create(
            RestoreJob(
                organization_id=organization_id, restore_kind=RestoreKind.FULL, started_at=NOW
            )
        )
        completed = await service.complete_job(
            job, is_validated=True, validation_summary="ok", now=NOW + timedelta(minutes=5)
        )
        assert completed.status is RestoreJobStatus.VALIDATED
        assert "RestoreCompleted" in publisher.names()

    async def test_fail_job(self, repos, organization_id: UUID, publisher) -> None:
        service = RestoreService(repos.restore_jobs, repos.restore_points, publish=publisher)
        job = await repos.restore_jobs.create(
            RestoreJob(organization_id=organization_id, restore_kind=RestoreKind.FULL)
        )
        failed = await service.fail_job(job, error_message="boom", now=NOW)
        assert failed.status is RestoreJobStatus.FAILED


class TestReplicationService:
    async def test_refresh_status_updates_from_lag(self, repos, organization_id: UUID) -> None:
        from app.models.enums import ReplicationMode, ReplicationScope
        from app.models.recovery import ReplicationJob

        target = await _target(repos, organization_id)
        job = await repos.replication_jobs.create(
            ReplicationJob(
                organization_id=organization_id,
                target_id=target.id,
                mode=ReplicationMode.ASYNCHRONOUS,
                scope=ReplicationScope.LOCAL,
                destination_ref="dest-1",
                lag_seconds=10.0,
            )
        )
        service = ReplicationService(
            repos.replication_jobs,
            warning_threshold_seconds=300.0,
            critical_threshold_seconds=1800.0,
        )
        updated = await service.refresh_status(job)
        assert updated.status.value == "in_sync"


class TestRetentionService:
    async def test_plan_for_policy_dry_run(self, repos, organization_id: UUID) -> None:
        from app.models.backup import BackupRetention

        policy = await repos.retention.create(
            BackupRetention(
                organization_id=organization_id, retention_days=90, archive_after_days=30
            )
        )
        service = RetentionService(repos.retention, repos.archives)
        plan = service.plan_for_policy(policy, [], now=NOW)
        assert plan.is_noop

    async def test_apply_plan_and_record_sweep(self, repos, organization_id: UUID) -> None:
        from app.models.backup import BackupRetention

        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=NOW - timedelta(days=100),
            )
        )
        policy = await repos.retention.create(
            BackupRetention(
                organization_id=organization_id, retention_days=90, archive_after_days=30
            )
        )
        service = RetentionService(repos.retention, repos.archives)
        plan = service.plan_for_policy(policy, [archive], now=NOW)
        deleted = await service.apply_plan(plan, {str(archive.id): archive})
        assert deleted == 1

        updated_policy = await service.record_sweep(
            organization_id, policy.id, applied_at=NOW, deleted_count=deleted
        )
        assert updated_policy.last_purged_count == 1

    async def test_apply_plan_tiers_archive_without_deleting(
        self, repos, organization_id: UUID
    ) -> None:
        from app.models.backup import BackupRetention
        from app.models.enums import RetentionTier

        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=NOW - timedelta(days=40),
                tier=RetentionTier.HOT,
            )
        )
        policy = await repos.retention.create(
            BackupRetention(
                organization_id=organization_id, retention_days=90, archive_after_days=30
            )
        )
        service = RetentionService(repos.retention, repos.archives)
        plan = service.plan_for_policy(policy, [archive], now=NOW)
        deleted = await service.apply_plan(plan, {str(archive.id): archive})
        assert deleted == 0
        assert archive.tier is RetentionTier.ARCHIVE


class TestVerificationService:
    async def test_verify_checksum_for_job_passed(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        service = VerificationService(repos.verifications)
        result = await service.verify_checksum_for_job(
            organization_id,
            job_id=job.id,
            archive_id=None,
            expected_checksum="abc",
            actual_checksum="abc",
            now=NOW,
        )
        assert result.status is VerificationStatus.PASSED
        assert result.error_message is None

    async def test_verify_checksum_for_job_failed_has_error_message(
        self, repos, organization_id: UUID
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        service = VerificationService(repos.verifications)
        result = await service.verify_checksum_for_job(
            organization_id,
            job_id=job.id,
            archive_id=None,
            expected_checksum="abc",
            actual_checksum="xyz",
            now=NOW,
        )
        assert result.status is VerificationStatus.FAILED
        assert result.error_message is not None


class TestDrPlanService:
    async def test_create_plan_computes_sequencing_label(
        self, repos, organization_id: UUID
    ) -> None:
        service = DrPlanService(repos.dr_plans)
        plan = await service.create_plan(
            organization_id,
            name="plan-1",
            description=None,
            priority=RecoveryPriority.HIGH,
            rpo_minutes=60,
            rto_minutes=120,
            recovery_groups=[{"name": "db"}, {"name": "api"}],
            dependencies={"api": ["db"]},
            owner="tester",
        )
        assert plan.labels["sequencing_valid"] == "True"

    async def test_create_plan_invalid_sequencing_labeled_false(
        self, repos, organization_id: UUID
    ) -> None:
        service = DrPlanService(repos.dr_plans)
        plan = await service.create_plan(
            organization_id,
            name="cyclic-plan",
            description=None,
            priority=RecoveryPriority.HIGH,
            rpo_minutes=60,
            rto_minutes=120,
            recovery_groups=[{"name": "a"}, {"name": "b"}],
            dependencies={"a": ["b"], "b": ["a"]},
            owner="tester",
        )
        assert plan.labels["sequencing_valid"] == "False"

    async def test_sequence_returns_order(self, repos, organization_id: UUID) -> None:
        service = DrPlanService(repos.dr_plans)
        plan = await service.create_plan(
            organization_id,
            name="plan-2",
            description=None,
            priority=RecoveryPriority.MEDIUM,
            rpo_minutes=60,
            rto_minutes=120,
            recovery_groups=[{"name": "db"}, {"name": "api"}],
            dependencies={"api": ["db"]},
            owner=None,
        )
        result = service.sequence(plan)
        assert result.order == ("db", "api")


class TestDrTestService:
    async def test_run_test_met_targets_passes(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        plan_service = DrPlanService(repos.dr_plans)
        plan = await plan_service.create_plan(
            organization_id,
            name="plan-1",
            description=None,
            priority=RecoveryPriority.HIGH,
            rpo_minutes=60,
            rto_minutes=120,
            recovery_groups=[],
            dependencies={},
            owner=None,
        )
        service = DrTestService(repos.dr_tests, repos.dr_plans, publish=publisher)
        test = await service.run_test(
            organization_id,
            dr_plan=plan,
            test_kind=DrTestKind.SIMULATION,
            achieved_rpo_minutes=30.0,
            achieved_rto_minutes=90.0,
            findings=[],
            summary="all good",
            started_at=NOW,
            completed_at=NOW + timedelta(minutes=10),
        )
        assert test.status.value == "passed"
        assert "DRTestCompleted" in publisher.names()

    async def test_run_test_violated_target_fails(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        plan_service = DrPlanService(repos.dr_plans)
        plan = await plan_service.create_plan(
            organization_id,
            name="plan-2",
            description=None,
            priority=RecoveryPriority.HIGH,
            rpo_minutes=60,
            rto_minutes=120,
            recovery_groups=[],
            dependencies={},
            owner=None,
        )
        service = DrTestService(repos.dr_tests, repos.dr_plans, publish=publisher)
        test = await service.run_test(
            organization_id,
            dr_plan=plan,
            test_kind=DrTestKind.SIMULATION,
            achieved_rpo_minutes=200.0,
            achieved_rto_minutes=90.0,
            findings=[],
            summary="rpo missed",
            started_at=NOW,
            completed_at=NOW + timedelta(minutes=10),
        )
        assert test.status.value == "failed"

    async def test_run_test_updates_plan_last_tested_at(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        plan_service = DrPlanService(repos.dr_plans)
        plan = await plan_service.create_plan(
            organization_id,
            name="plan-3",
            description=None,
            priority=RecoveryPriority.HIGH,
            rpo_minutes=60,
            rto_minutes=120,
            recovery_groups=[],
            dependencies={},
            owner=None,
        )
        service = DrTestService(repos.dr_tests, repos.dr_plans, publish=publisher)
        completed_at = NOW + timedelta(minutes=10)
        await service.run_test(
            organization_id,
            dr_plan=plan,
            test_kind=DrTestKind.SIMULATION,
            achieved_rpo_minutes=30.0,
            achieved_rto_minutes=90.0,
            findings=[],
            summary=None,
            started_at=NOW,
            completed_at=completed_at,
        )
        refreshed = await repos.dr_plans.require_by_id(plan.id)
        assert refreshed.last_tested_at == completed_at


class TestRecoveryReportService:
    async def test_generate_for_test_met_compliance(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        plan = await repos.dr_plans.create(
            DrPlan(organization_id=organization_id, name="plan", rpo_minutes=60, rto_minutes=120)
        )
        test = await repos.dr_tests.create(
            DrTest(
                organization_id=organization_id,
                dr_plan_id=plan.id,
                test_kind=DrTestKind.SIMULATION,
                rpo_status=ComplianceStatus.MET,
                rto_status=ComplianceStatus.MET,
            )
        )
        service = RecoveryReportService(repos.recovery_reports, publish=publisher)
        report = await service.generate_for_test(organization_id, test, plan, now=NOW)
        assert report.compliance_status.value == "met"
        assert "RecoveryValidated" in publisher.names()

    async def test_generate_for_test_violated_when_either_violated(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        plan = await repos.dr_plans.create(
            DrPlan(organization_id=organization_id, name="plan", rpo_minutes=60, rto_minutes=120)
        )
        test = await repos.dr_tests.create(
            DrTest(
                organization_id=organization_id,
                dr_plan_id=plan.id,
                test_kind=DrTestKind.SIMULATION,
                rpo_status=ComplianceStatus.VIOLATED,
                rto_status=ComplianceStatus.MET,
            )
        )
        service = RecoveryReportService(repos.recovery_reports, publish=publisher)
        report = await service.generate_for_test(organization_id, test, plan, now=NOW)
        assert report.compliance_status.value == "violated"

    async def test_generate_for_test_not_measured_otherwise(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        plan = await repos.dr_plans.create(
            DrPlan(organization_id=organization_id, name="plan", rpo_minutes=60, rto_minutes=120)
        )
        test = await repos.dr_tests.create(
            DrTest(
                organization_id=organization_id,
                dr_plan_id=plan.id,
                test_kind=DrTestKind.SIMULATION,
                rpo_status=ComplianceStatus.NOT_MEASURED,
                rto_status=ComplianceStatus.NOT_MEASURED,
            )
        )
        service = RecoveryReportService(repos.recovery_reports, publish=publisher)
        report = await service.generate_for_test(organization_id, test, plan, now=NOW)
        assert report.compliance_status.value == "not_measured"


class TestFailoverService:
    def test_authorize_manual_always_authorized(self, repos) -> None:
        service = FailoverService(repos.failover_events)
        result = service.authorize(FailoverKind.MANUAL, [])
        assert result.is_authorized

    def test_authorize_automatic_needs_healthy_checks(self, repos) -> None:
        service = FailoverService(repos.failover_events)
        result = service.authorize(
            FailoverKind.AUTOMATIC,
            [HealthCheckResult(check_name="db", is_healthy=False, detail="")],
        )
        assert not result.is_authorized

    async def test_initiate_publishes_event(self, repos, organization_id: UUID, publisher) -> None:
        service = FailoverService(repos.failover_events, publish=publisher)
        event = await service.initiate(
            organization_id,
            dr_plan_id=None,
            kind=FailoverKind.MANUAL,
            source_ref="primary",
            target_ref="standby",
            initiated_by="tester",
            health_checks=[],
            now=NOW,
        )
        assert event.status is FailoverStatus.HEALTH_CHECKING
        assert "FailoverStarted" in publisher.names()

    async def test_complete_success(self, repos, organization_id: UUID, publisher) -> None:
        service = FailoverService(repos.failover_events, publish=publisher)
        event = await repos.failover_events.create(
            FailoverEvent(
                organization_id=organization_id,
                failover_kind=FailoverKind.MANUAL,
                initiated_at=NOW,
            )
        )
        completed = await service.complete(
            event,
            succeeded=True,
            was_rolled_back=False,
            error_message=None,
            now=NOW + timedelta(minutes=1),
        )
        assert completed.status is FailoverStatus.COMPLETED
        assert "FailoverCompleted" in publisher.names()

    async def test_complete_failure(self, repos, organization_id: UUID, publisher) -> None:
        service = FailoverService(repos.failover_events, publish=publisher)
        event = await repos.failover_events.create(
            FailoverEvent(
                organization_id=organization_id,
                failover_kind=FailoverKind.MANUAL,
                initiated_at=NOW,
            )
        )
        completed = await service.complete(
            event,
            succeeded=False,
            was_rolled_back=True,
            error_message="unreachable",
            now=NOW + timedelta(minutes=1),
        )
        assert completed.status is FailoverStatus.FAILED
        assert completed.was_rolled_back


class TestStatisticsService:
    async def test_roll_up_window_creates_then_updates_idempotently(
        self, repos, organization_id: UUID
    ) -> None:
        service = StatisticsService(repos.statistics)
        window_end = NOW + timedelta(hours=1)
        first = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=window_end,
            jobs_completed=5,
            jobs_failed=1,
            bytes_backed_up=1024,
            restore_jobs_completed=2,
            restore_jobs_failed=0,
            mean_restore_duration_ms=100.0,
            replication_jobs_lagging=0,
            mean_replication_lag_seconds=None,
            rpo_compliant_count=1,
            rpo_violated_count=0,
            rto_compliant_count=1,
            rto_violated_count=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=window_end,
            jobs_completed=10,
            jobs_failed=2,
            bytes_backed_up=2048,
            restore_jobs_completed=3,
            restore_jobs_failed=1,
            mean_restore_duration_ms=150.0,
            replication_jobs_lagging=1,
            mean_replication_lag_seconds=5.0,
            rpo_compliant_count=2,
            rpo_violated_count=1,
            rto_compliant_count=2,
            rto_violated_count=0,
        )
        assert first.id == second.id
        assert second.jobs_completed == 10


class TestReportService:
    async def test_generate(self, repos, organization_id: UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.BACKUP,
            title="Monthly Backup Report",
            report_format=ReportFormat.JSON,
            period_start=NOW - timedelta(days=30),
            period_end=NOW,
            content={"total_jobs": 100},
            row_count=100,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"


class TestImmutabilityService:
    async def test_lock_extends_and_records_audit(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id, job_id=job.id, storage_ref="ref-1", archived_at=NOW
            )
        )
        audit = AuditService(repos.audit)
        service = ImmutabilityService(repos.archives, audit=audit)
        outcome = await service.lock(
            archive, until=NOW + timedelta(days=30), actor_id="tester", now=NOW
        )
        assert outcome.accepted
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 1

    async def test_lock_shortening_refused_no_audit(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=NOW,
                retention_lock_until=NOW + timedelta(days=30),
            )
        )
        audit = AuditService(repos.audit)
        service = ImmutabilityService(repos.archives, audit=audit)
        outcome = await service.lock(
            archive, until=NOW + timedelta(days=5), actor_id="tester", now=NOW
        )
        assert not outcome.accepted
        assert outcome.refusal == LockRefusal.WOULD_SHORTEN_EXISTING_LOCK
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 0

    async def test_apply_legal_hold(self, repos, organization_id: UUID) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id, job_id=job.id, storage_ref="ref-1", archived_at=NOW
            )
        )
        audit = AuditService(repos.audit)
        service = ImmutabilityService(repos.archives, audit=audit)
        updated = await service.apply_legal_hold(
            archive, reason="litigation", actor_id="tester", now=NOW
        )
        assert updated.legal_hold
        assert updated.legal_hold_reason == "litigation"

    async def test_release_legal_hold_falls_back_to_lock(
        self, repos, organization_id: UUID
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=NOW,
                legal_hold=True,
                retention_lock_until=NOW + timedelta(days=10),
            )
        )
        service = ImmutabilityService(repos.archives)
        updated = await service.release_legal_hold(archive, actor_id="tester", now=NOW)
        assert not updated.legal_hold
        assert updated.immutability_state.value == "retention_locked"

    async def test_release_legal_hold_no_underlying_lock(
        self, repos, organization_id: UUID
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=NOW,
                legal_hold=True,
            )
        )
        service = ImmutabilityService(repos.archives)
        updated = await service.release_legal_hold(archive, actor_id="tester", now=NOW)
        assert updated.immutability_state.value == "none"

    async def test_release_legal_hold_with_audit_records_entry(
        self, repos, organization_id: UUID
    ) -> None:
        target = await _target(repos, organization_id)
        job = await _job(repos, organization_id, target.id)
        archive = await repos.archives.create(
            BackupArchive(
                organization_id=organization_id,
                job_id=job.id,
                storage_ref="ref-1",
                archived_at=NOW,
                legal_hold=True,
            )
        )
        audit = AuditService(repos.audit)
        service = ImmutabilityService(repos.archives, audit=audit)
        await service.release_legal_hold(archive, actor_id="tester", now=NOW)
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 1
