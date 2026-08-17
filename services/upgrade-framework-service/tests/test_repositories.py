"""Integration tests for every repository, against real PostgreSQL."""

from __future__ import annotations

import uuid

from app.models.compatibility import CompatibilityMatrixEntry
from app.models.enums import (
    CheckResultStatus,
    CompatibilityType,
    MigrationType,
    ReleaseChannelType,
    ReportFormat,
    ReportStatus,
    UpgradeAuditAction,
    UpgradeJobStatus,
    UpgradeReportKind,
    UpgradeStrategy,
    UpgradeTargetStatus,
    UpgradeTargetType,
    VerificationCheckType,
)
from app.models.migrations import ConfigurationMigration, MigrationHistory, PluginMigration
from app.models.releases import ReleaseChannel, ReleaseVersion
from app.models.reporting import UpgradeAudit, UpgradeReport, UpgradeStatistic
from app.models.rollback import RollbackHistory
from app.models.upgrade import (
    UpgradeDependency,
    UpgradeHistory,
    UpgradeJob,
    UpgradePlan,
    UpgradeResult,
    UpgradeTarget,
)
from app.models.verification import VerificationResult
from app.services.bundle import Repositories
from tests.conftest import hours_ago, utcnow


class TestReleaseRepositories:
    async def test_channel_find_by_name_list_enabled_and_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.channels.create(
            ReleaseChannel(
                organization_id=organization_id,
                name="stable",
                channel_type=ReleaseChannelType.STABLE,
            )
        )
        found = await repos.channels.find_by_name(organization_id, name="stable")
        assert found is not None
        assert len(await repos.channels.list_enabled(organization_id)) == 1
        assert len(await repos.channels.list_all(organization_id)) == 1

    async def test_version_find_current_list_latest_all_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        channel = await repos.channels.create(
            ReleaseChannel(
                organization_id=organization_id,
                name="stable2",
                channel_type=ReleaseChannelType.STABLE,
            )
        )
        older = await repos.versions.create(
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
                released_at=hours_ago(1),
            )
        )
        current = await repos.versions.find_current(organization_id, release_channel_id=channel.id)
        assert current is not None
        assert current.id == older.id
        latest = await repos.versions.list_latest(
            organization_id, release_channel_id=channel.id, limit=1
        )
        assert latest[0].version_label == "1.1.0"
        assert len(await repos.versions.list_for_channel(channel.id)) == 2
        assert len(await repos.versions.list_all(organization_id)) == 2
        assert organization_id in await repos.versions.list_organization_ids()


class TestUpgradeRepositories:
    async def test_plan_find_by_name_and_list_enabled(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan1",
                target_type=UpgradeTargetType.PLATFORM_SERVICE,
                strategy=UpgradeStrategy.ROLLING,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        found = await repos.plans.find_by_name(organization_id, name="plan1")
        assert found is not None
        assert len(await repos.plans.list_enabled(organization_id)) == 1

    async def test_job_list_recent_running_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan2",
                target_type=UpgradeTargetType.PLUGIN,
                strategy=UpgradeStrategy.CANARY,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        await repos.jobs.create(
            UpgradeJob(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                status=UpgradeJobStatus.RUNNING,
            )
        )
        assert (
            len(await repos.jobs.list_recent(organization_id, status=UpgradeJobStatus.RUNNING)) == 1
        )
        assert len(await repos.jobs.list_running(organization_id)) == 1
        assert organization_id in await repos.jobs.list_organization_ids()

    async def test_history_list_for_job_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan3",
                target_type=UpgradeTargetType.SDK,
                strategy=UpgradeStrategy.SEQUENTIAL,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.history.create(
            UpgradeHistory(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                event_type="started",
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.history.list_for_job(job.id)) == 1
        assert len(await repos.history.list_recent(organization_id)) == 1

    async def test_target_list_for_job(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan4",
                target_type=UpgradeTargetType.EDGE_DEVICE,
                strategy=UpgradeStrategy.PARALLEL,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.targets.create(
            UpgradeTarget(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                target_ref="edge-1",
                target_type=UpgradeTargetType.EDGE_DEVICE,
            )
        )
        assert len(await repos.targets.list_for_job(job.id)) == 1

    async def test_result_list_for_target(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan5",
                target_type=UpgradeTargetType.CLOUD_RESOURCE,
                strategy=UpgradeStrategy.ZERO_DOWNTIME,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        target = await repos.targets.create(
            UpgradeTarget(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                target_ref="res-1",
                target_type=UpgradeTargetType.CLOUD_RESOURCE,
            )
        )
        await repos.results.create(
            UpgradeResult(
                organization_id=organization_id,
                upgrade_target_id=target.id,
                status=UpgradeTargetStatus.SUCCEEDED,
                completed_at=utcnow(),
            )
        )
        assert len(await repos.results.list_for_target(target.id)) == 1

    async def test_dependency_list_for_plan(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan6",
                target_type=UpgradeTargetType.CLI,
                strategy=UpgradeStrategy.MANUAL_APPROVAL,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        await repos.dependencies.create(
            UpgradeDependency(
                organization_id=organization_id,
                upgrade_plan_id=plan.id,
                dependency_name="postgres",
                required_version="15.0.0",
                status=CheckResultStatus.PASSED,
            )
        )
        assert len(await repos.dependencies.list_for_plan(plan.id)) == 1


class TestCompatibilityRepository:
    async def test_find_entry_list_for_version_pair_and_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.compatibility.create(
            CompatibilityMatrixEntry(
                organization_id=organization_id,
                from_version="1.0.0",
                to_version="1.1.0",
                compatibility_type=CompatibilityType.API,
                status=CheckResultStatus.PASSED,
            )
        )
        found = await repos.compatibility.find_entry(
            organization_id,
            from_version="1.0.0",
            to_version="1.1.0",
            compatibility_type=CompatibilityType.API,
        )
        assert found is not None
        assert (
            len(
                await repos.compatibility.list_for_version_pair(
                    organization_id, from_version="1.0.0", to_version="1.1.0"
                )
            )
            == 1
        )
        assert len(await repos.compatibility.list_all(organization_id)) == 1


class TestMigrationsRepositories:
    async def test_migration_history_list_for_job_running_recent_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan7",
                target_type=UpgradeTargetType.DATABASE,
                strategy=UpgradeStrategy.ROLLING,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.migration_history.create(
            MigrationHistory(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                migration_type=MigrationType.DATABASE_SCHEMA,
                status=UpgradeJobStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        assert len(await repos.migration_history.list_for_job(job.id)) == 1
        assert len(await repos.migration_history.list_running(organization_id)) == 1
        assert len(await repos.migration_history.list_recent(organization_id)) == 1
        assert organization_id in await repos.migration_history.list_organization_ids()

    async def test_configuration_migration_list_for_job(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan8",
                target_type=UpgradeTargetType.CONFIGURATION,
                strategy=UpgradeStrategy.ROLLING,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.configuration_migrations.create(
            ConfigurationMigration(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                config_key="feature.flag",
                old_value={"enabled": False},
                new_value={"enabled": True},
                applied_at=utcnow(),
            )
        )
        assert len(await repos.configuration_migrations.list_for_job(job.id)) == 1

    async def test_plugin_migration_list_for_job(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan9",
                target_type=UpgradeTargetType.PLUGIN,
                strategy=UpgradeStrategy.ROLLING,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.plugin_migrations.create(
            PluginMigration(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                plugin_name="my-plugin",
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        assert len(await repos.plugin_migrations.list_for_job(job.id)) == 1


class TestRollbackRepository:
    async def test_list_for_job_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan10",
                target_type=UpgradeTargetType.PLATFORM,
                strategy=UpgradeStrategy.ROLLING,
                from_version="2.0.0",
                to_version="1.0.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.rollback_history.create(
            RollbackHistory(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                from_version="2.0.0",
                to_version="1.0.0",
            )
        )
        assert len(await repos.rollback_history.list_for_job(job.id)) == 1
        assert len(await repos.rollback_history.list_recent(organization_id)) == 1


class TestVerificationRepository:
    async def test_list_for_job_failed_for_job_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        plan = await repos.plans.create(
            UpgradePlan(
                organization_id=organization_id,
                name="plan11",
                target_type=UpgradeTargetType.AI_MODEL,
                strategy=UpgradeStrategy.ROLLING,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        job = await repos.jobs.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=plan.id)
        )
        await repos.verification_results.create(
            VerificationResult(
                organization_id=organization_id,
                upgrade_job_id=job.id,
                check_type=VerificationCheckType.HEALTH,
                status=CheckResultStatus.FAILED,
                verified_at=utcnow(),
            )
        )
        assert len(await repos.verification_results.list_for_job(job.id)) == 1
        assert len(await repos.verification_results.list_failed_for_job(job.id)) == 1
        assert len(await repos.verification_results.list_recent(organization_id)) == 1


class TestReportingRepositories:
    async def test_statistic_find_window_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = utcnow()
        await repos.statistics.create(
            UpgradeStatistic(
                organization_id=organization_id, window_start=window_start, window_end=utcnow()
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        assert len(await repos.statistics.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_list_recent_filters(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            UpgradeReport(
                organization_id=organization_id,
                kind=UpgradeReportKind.UPGRADE,
                report_format=ReportFormat.JSON,
                title="Upgrade report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        assert (
            len(await repos.reports.list_recent(organization_id, kind=UpgradeReportKind.UPGRADE))
            == 1
        )
        assert (
            len(await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED))
            == 1
        )

    async def test_audit_list_recent_for_entity_and_since(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            UpgradeAudit(
                organization_id=organization_id,
                action=UpgradeAuditAction.ADMINISTRATIVE,
                entity_type="x",
                entity_id=entity_id,
                summary="s",
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.audit.list_recent(organization_id)) == 1
        assert len(await repos.audit.list_for_entity("x", entity_id)) == 1
        assert len(await repos.audit.list_recent(organization_id, since=hours_ago(1))) == 1
        assert len(await repos.audit.list_recent(organization_id, since=hours_ago(-1))) == 0
