"""Unit/integration tests for every service, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    CheckResultStatus,
    CompatibilityType,
    MigrationType,
    ReleaseChannelType,
    UpgradeAuditAction,
    UpgradeJobStatus,
    UpgradeReportKind,
    UpgradeStrategy,
    UpgradeTargetStatus,
    UpgradeTargetType,
    VerificationCheckType,
)
from app.services import migrations as migrations_services
from app.services import upgrade as upgrade_services
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.compatibility import CompatibilityService
from app.services.dependencies import UpgradeDependencyService
from app.services.fleet import FleetUpgradeService, UpgradeResultService
from app.services.migrations import (
    ConfigurationMigrationService,
    MigrationService,
    PluginMigrationService,
)
from app.services.releases import ReleaseChannelService, ReleaseVersionService
from app.services.reports import ReportService
from app.services.rollback import InvalidRollbackTargetError, RollbackService
from app.services.simulation import SimulationService
from app.services.statistics import StatisticsService
from app.services.upgrade import UpgradeExecutionService, UpgradeJobService, UpgradePlanService
from app.services.verification import VerificationService
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


async def _make_plan(repos: Repositories, organization_id: uuid.UUID, name: str = "p1"):
    service = UpgradePlanService(repos.plans)
    return await service.create(
        organization_id,
        name=name,
        target_type=UpgradeTargetType.PLATFORM_SERVICE,
        strategy=UpgradeStrategy.ROLLING,
        from_version="1.0.0",
        to_version="1.1.0",
    )


class TestReleaseServices:
    async def test_channel_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReleaseChannelService(repos.channels)
        channel = await service.create(
            organization_id, name="stable", channel_type=ReleaseChannelType.STABLE
        )
        assert channel.name == "stable"

    async def test_version_publish_and_mark_current(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        channel_service = ReleaseChannelService(repos.channels)
        channel = await channel_service.create(
            organization_id, name="beta", channel_type=ReleaseChannelType.BETA
        )
        version_service = ReleaseVersionService(repos.versions, publish=publisher)
        first = await version_service.publish(
            organization_id,
            release_channel_id=channel.id,
            version_label="1.0.0",
            released_at=hours_ago(2),
        )
        second = await version_service.publish(
            organization_id,
            release_channel_id=channel.id,
            version_label="1.1.0",
            released_at=hours_ago(1),
        )
        assert "ReleasePublished" in publisher.names()
        await version_service.mark_current(first)
        marked = await version_service.mark_current(second)
        assert marked.is_current is True
        rows = await repos.versions.list_for_channel(channel.id)
        first_row = next(row for row in rows if row.version_label == "1.0.0")
        assert first_row.is_current is False


class TestUpgradeServices:
    async def test_job_service_create_start_complete(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id)
        service = UpgradeJobService(repos.jobs, repos.history)
        job = await service.create(organization_id, upgrade_plan_id=plan.id)
        job = await service.start(job, now=utcnow())
        assert job.status == "running"
        assert len(await repos.history.list_for_job(job.id)) == 1
        job = await service.complete(job, status=UpgradeJobStatus.SUCCEEDED, now=utcnow())
        assert job.status == "succeeded"
        assert len(await repos.history.list_for_job(job.id)) == 2

    async def test_job_service_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="p2")
        service = UpgradeJobService(repos.jobs, repos.history)
        job = await service.create(organization_id, upgrade_plan_id=plan.id)
        with pytest.raises(upgrade_services.TransitionRefusedError):
            await service.complete(job, status=UpgradeJobStatus.SUCCEEDED, now=utcnow())

    async def test_execution_service_schedule_start_and_complete_succeeded(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="p3")
        job_service = UpgradeJobService(repos.jobs, repos.history)
        execution_service = UpgradeExecutionService(
            job_service, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        job = await execution_service.schedule_and_start(
            organization_id, upgrade_plan_id=plan.id, plan_name="p3", now=utcnow()
        )
        assert "UpgradeScheduled" in publisher.names()
        assert "UpgradeStarted" in publisher.names()
        assert ("notify_upgrade_scheduled", {"plan_name": "p3"}) in notifier.calls

        completed = await execution_service.complete(
            job, status=UpgradeJobStatus.SUCCEEDED, now=utcnow()
        )
        assert completed.status == "succeeded"
        assert "UpgradeCompleted" in publisher.names()
        assert "UpgradeFailed" not in publisher.names()

    async def test_execution_service_complete_failed_notifies(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="p4")
        job_service = UpgradeJobService(repos.jobs, repos.history)
        execution_service = UpgradeExecutionService(
            job_service, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        job = await execution_service.schedule_and_start(
            organization_id, upgrade_plan_id=plan.id, plan_name="p4", now=utcnow()
        )
        completed = await execution_service.complete(
            job, status=UpgradeJobStatus.FAILED, now=utcnow(), error_message="disk full"
        )
        assert completed.status == "failed"
        assert "UpgradeFailed" in publisher.names()
        assert ("notify_upgrade_failed", {"reason": "disk full"}) in notifier.calls


class TestCompatibilityService:
    async def test_validate_notifies_on_issue(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = CompatibilityService(repos.compatibility, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        entry = await service.validate(
            organization_id,
            from_version="1.0.0",
            to_version="1.0.0",
            compatibility_type=CompatibilityType.API,
        )
        assert entry.status == "failed"
        assert "CompatibilityValidated" in publisher.names()
        assert any(call[0] == "notify_compatibility_issue" for call in notifier.calls)

    async def test_validate_upserts_same_version_pair_and_type(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = CompatibilityService(repos.compatibility)
        first = await service.validate(
            organization_id,
            from_version="1.0.0",
            to_version="1.1.0",
            compatibility_type=CompatibilityType.API,
            detail="initial check",
        )
        second = await service.validate(
            organization_id,
            from_version="1.0.0",
            to_version="1.1.0",
            compatibility_type=CompatibilityType.API,
            detail="rechecked",
        )
        assert second.id == first.id
        assert second.status == "passed"
        assert second.detail == "rechecked"
        assert len(await repos.compatibility.list_all(organization_id)) == 1


class TestUpgradeDependencyService:
    async def test_check_classifies_and_records(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="p5")
        service = UpgradeDependencyService(repos.dependencies)
        result = await service.check(
            organization_id,
            upgrade_plan_id=plan.id,
            dependency_name="postgres",
            required_version="15.0.0",
            found_version="14.0.0",
        )
        assert result.status == "failed"


class TestRollbackService:
    async def test_initiate_rejects_unknown_target(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="rb1")
        job_service = UpgradeJobService(repos.jobs, repos.history)
        service = RollbackService(repos.rollback_history, job_service)
        with pytest.raises(InvalidRollbackTargetError):
            await service.initiate(
                organization_id,
                upgrade_plan_id=plan.id,
                current_version="2.0.0",
                target_version="1.0.0",
                available_versions=["2.0.0"],
                now=utcnow(),
            )

    async def test_initiate_and_complete_notifies(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="rb2")
        job_service = UpgradeJobService(repos.jobs, repos.history)
        service = RollbackService(
            repos.rollback_history, job_service, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        history = await service.initiate(
            organization_id,
            upgrade_plan_id=plan.id,
            current_version="2.0.0",
            target_version="1.0.0",
            available_versions=["1.0.0", "2.0.0"],
            reason="bad release",
            now=utcnow(),
        )
        assert "RollbackStarted" in publisher.names()
        job = await repos.jobs.require_by_id(history.upgrade_job_id)
        completed = await service.complete(
            history, job, status=UpgradeJobStatus.SUCCEEDED, now=utcnow()
        )
        assert completed.status == "succeeded"
        assert "RollbackCompleted" in publisher.names()
        assert ("notify_rollback_completed", {"to_version": "1.0.0"}) in notifier.calls


class TestMigrationsServices:
    async def test_migration_service_start_complete_and_notifies_on_failure(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="mig1")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        service = MigrationService(repos.migration_history, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        migration = await service.start(
            organization_id,
            upgrade_job_id=job.id,
            migration_type=MigrationType.DATABASE_SCHEMA,
            now=utcnow(),
        )
        completed = await service.complete(migration, status=UpgradeJobStatus.FAILED, now=utcnow())
        assert completed.status == "failed"
        assert "MigrationCompleted" in publisher.names()
        assert any(call[0] == "notify_migration_failed" for call in notifier.calls)

    async def test_migration_service_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="mig2")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        service = MigrationService(repos.migration_history)
        migration = await service.start(
            organization_id,
            upgrade_job_id=job.id,
            migration_type=MigrationType.PLUGIN,
            now=utcnow(),
        )
        await service.complete(migration, status=UpgradeJobStatus.SUCCEEDED, now=utcnow())
        with pytest.raises(migrations_services.TransitionRefusedError):
            await service.complete(migration, status=UpgradeJobStatus.FAILED, now=utcnow())

    async def test_configuration_migration_record(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="mig3")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        service = ConfigurationMigrationService(repos.configuration_migrations)
        record = await service.record(
            organization_id,
            upgrade_job_id=job.id,
            config_key="feature.flag",
            old_value={"enabled": False},
            new_value={"enabled": True},
            now=utcnow(),
        )
        assert record.config_key == "feature.flag"

    async def test_plugin_migration_record(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="mig4")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        service = PluginMigrationService(repos.plugin_migrations)
        record = await service.record(
            organization_id,
            upgrade_job_id=job.id,
            plugin_name="my-plugin",
            from_version="1.0.0",
            to_version="1.1.0",
        )
        assert record.plugin_name == "my-plugin"


class TestVerificationService:
    async def test_record_result_and_compute_overall(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="ver1")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        service = VerificationService(repos.verification_results)
        await service.record_result(
            organization_id,
            upgrade_job_id=job.id,
            check_type=VerificationCheckType.HEALTH,
            status=CheckResultStatus.PASSED,
            now=utcnow(),
        )
        await service.record_result(
            organization_id,
            upgrade_job_id=job.id,
            check_type=VerificationCheckType.API,
            status=CheckResultStatus.FAILED,
            now=utcnow(),
        )
        overall = await service.compute_overall(job.id)
        assert overall == CheckResultStatus.FAILED


class TestSimulationService:
    def test_simulate_computes_risk_and_duration(self) -> None:
        service = SimulationService()
        outcome = service.simulate(
            compatibility_results=[CheckResultStatus.PASSED],
            dependency_results=[CheckResultStatus.WARNING],
            target_count=5,
            seconds_per_target=10.0,
        )
        assert outcome.risk_level == "medium"
        assert outcome.estimated_duration_seconds == 50.0
        assert outcome.check_count == 2


class TestFleetServices:
    async def test_plan_targets_and_mark_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await _make_plan(repos, organization_id, name="fleet1")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        service = FleetUpgradeService(repos.targets)
        targets = await service.plan_targets(
            organization_id,
            upgrade_job_id=job.id,
            target_refs=["edge-1", "edge-2", "edge-3"],
            target_type=UpgradeTargetType.EDGE_DEVICE,
            wave_size=2,
        )
        assert len(targets) == 3
        assert targets[0].wave_number == 0
        assert targets[2].wave_number == 1
        updated = await service.mark_status(targets[0], status=UpgradeTargetStatus.SUCCEEDED)
        assert updated.status == "succeeded"

    async def test_result_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        plan = await _make_plan(repos, organization_id, name="fleet2")
        job = await UpgradeJobService(repos.jobs, repos.history).create(
            organization_id, upgrade_plan_id=plan.id
        )
        target_service = FleetUpgradeService(repos.targets)
        targets = await target_service.plan_targets(
            organization_id,
            upgrade_job_id=job.id,
            target_refs=["edge-1"],
            target_type=UpgradeTargetType.EDGE_DEVICE,
            wave_size=1,
        )
        service = UpgradeResultService(repos.results)
        result = await service.record(
            organization_id,
            upgrade_target_id=targets[0].id,
            status=UpgradeTargetStatus.SUCCEEDED,
            now=utcnow(),
        )
        assert result.status == "succeeded"


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
            upgrade_count=1,
            rollback_count=0,
            migration_count=0,
            compatibility_failure_count=0,
            success_count=0,
            failure_count=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            upgrade_count=5,
            rollback_count=0,
            migration_count=0,
            compatibility_failure_count=0,
            success_count=0,
            failure_count=0,
        )
        assert first.id == second.id
        assert second.upgrade_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=UpgradeReportKind.UPGRADE,
            title="Upgrade report",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=5,
            now=utcnow(),
        )
        assert report.status == "completed"
        assert report.row_count == 5


class TestAuditService:
    async def test_record_and_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=UpgradeAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"
