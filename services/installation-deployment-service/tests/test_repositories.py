"""Integration tests for every repository, against real PostgreSQL."""

from __future__ import annotations

import uuid

from app.models.configuration import ConfigurationProfile
from app.models.deployment import (
    DeploymentArtifact,
    DeploymentHistory,
    DeploymentInventory,
    DeploymentJob,
    DeploymentProfile,
    DeploymentStatusRecord,
    DeploymentTarget,
    DeploymentVersion,
)
from app.models.enums import (
    CheckResultStatus,
    ConfigurationSection,
    DeploymentAuditAction,
    DeploymentEngine,
    DeploymentJobStatus,
    DeploymentJobType,
    DeploymentReportKind,
    DeploymentStrategy,
    DeploymentTargetType,
    InstallationMode,
    InstallationSessionStatus,
    PreflightCheckType,
    ReportFormat,
    ReportStatus,
    SecretStatus,
    SecretType,
    TlsCertificateStatus,
    VerificationCheckType,
)
from app.models.installation import InstallationLog, InstallationSession
from app.models.reporting import DeploymentAudit, DeploymentReport, DeploymentStatistic
from app.models.secrets_tls import GeneratedSecret, TlsCertificate
from app.models.upgrade_rollback import RollbackHistory, UpgradeHistory
from app.models.validation import DependencyCheck, PreflightResult
from app.models.verification import VerificationResult
from app.services.bundle import Repositories
from tests.conftest import hours_ago, utcnow


class TestDeploymentRepositories:
    async def test_profile_find_by_name_and_list_enabled(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="prod",
                target_type=DeploymentTargetType.MULTI_NODE_KUBERNETES,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.HELM,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        found = await repos.profiles.find_by_name(organization_id, name="prod")
        assert found is not None
        assert len(await repos.profiles.list_enabled(organization_id)) == 1
        assert organization_id in await repos.profiles.list_organization_ids()

    async def test_target_list_for_profile_and_organization(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p1",
                target_type=DeploymentTargetType.DOCKER_COMPOSE,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.DOCKER_COMPOSE,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        await repos.targets.create(
            DeploymentTarget(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                name="t1",
                target_type=DeploymentTargetType.DOCKER_COMPOSE,
            )
        )
        assert len(await repos.targets.list_for_profile(profile.id)) == 1
        assert len(await repos.targets.list_for_organization(organization_id)) == 1

    async def test_inventory_list_for_target(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p2",
                target_type=DeploymentTargetType.BARE_METAL,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.KUBERNETES_MANIFEST,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        target = await repos.targets.create(
            DeploymentTarget(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                name="t2",
                target_type=DeploymentTargetType.BARE_METAL,
            )
        )
        await repos.inventory.create(
            DeploymentInventory(
                organization_id=organization_id, deployment_target_id=target.id, node_name="node-1"
            )
        )
        assert len(await repos.inventory.list_for_target(target.id)) == 1

    async def test_job_list_recent_running_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p3",
                target_type=DeploymentTargetType.LOCAL_DEVELOPMENT,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.DOCKER_COMPOSE,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
                status=DeploymentJobStatus.RUNNING,
            )
        )
        assert (
            len(await repos.jobs.list_recent(organization_id, job_type=DeploymentJobType.DEPLOY))
            == 1
        )
        assert len(await repos.jobs.list_running(organization_id)) == 1
        assert organization_id in await repos.jobs.list_organization_ids()

    async def test_history_list_for_job(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p4",
                target_type=DeploymentTargetType.EDGE,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.HELM,
                strategy=DeploymentStrategy.CANARY,
            )
        )
        job = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
            )
        )
        await repos.history.create(
            DeploymentHistory(
                organization_id=organization_id,
                deployment_job_id=job.id,
                event_type="started",
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.history.list_for_job(job.id)) == 1

    async def test_version_find_current_list_latest_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        older = await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                released_at=hours_ago(48),
                is_current=True,
            )
        )
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id, version_label="1.1.0", released_at=hours_ago(1)
            )
        )
        current = await repos.versions.find_current(organization_id)
        assert current is not None
        assert current.id == older.id
        latest = await repos.versions.list_latest(organization_id, limit=1)
        assert latest[0].version_label == "1.1.0"
        found = await repos.versions.find_by_label(organization_id, version_label="1.1.0")
        assert found is not None
        assert len(await repos.versions.list_all(organization_id)) == 2
        assert organization_id in await repos.versions.list_organization_ids()

    async def test_artifact_list_for_version(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id, version_label="2.0.0", released_at=utcnow()
            )
        )
        await repos.artifacts.create(
            DeploymentArtifact(
                organization_id=organization_id,
                deployment_version_id=version.id,
                artifact_type="container_image",
                checksum_sha256="a" * 64,
            )
        )
        assert len(await repos.artifacts.list_for_version(version.id)) == 1

    async def test_status_board_find_and_list(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p5",
                target_type=DeploymentTargetType.PRIVATE_CLOUD,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.HELM,
                strategy=DeploymentStrategy.BLUE_GREEN,
            )
        )
        target = await repos.targets.create(
            DeploymentTarget(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                name="t5",
                target_type=DeploymentTargetType.PRIVATE_CLOUD,
            )
        )
        await repos.status_board.create(
            DeploymentStatusRecord(
                organization_id=organization_id,
                deployment_target_id=target.id,
                status=DeploymentJobStatus.SUCCEEDED,
                updated_at_status=utcnow(),
            )
        )
        found = await repos.status_board.find_for_target(
            organization_id, deployment_target_id=target.id
        )
        assert found is not None
        assert len(await repos.status_board.list_for_organization(organization_id)) == 1


class TestInstallationRepositories:
    async def test_session_list_running_recent_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.installation_sessions.create(
            InstallationSession(
                organization_id=organization_id,
                mode=InstallationMode.CLI,
                status=InstallationSessionStatus.RUNNING,
            )
        )
        assert len(await repos.installation_sessions.list_running(organization_id)) == 1
        assert len(await repos.installation_sessions.list_recent(organization_id)) == 1
        assert organization_id in await repos.installation_sessions.list_organization_ids()

    async def test_log_list_for_session(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        session = await repos.installation_sessions.create(
            InstallationSession(organization_id=organization_id, mode=InstallationMode.SILENT)
        )
        await repos.installation_logs.create(
            InstallationLog(
                organization_id=organization_id,
                installation_session_id=session.id,
                message="starting",
                logged_at=utcnow(),
            )
        )
        assert len(await repos.installation_logs.list_for_session(session.id)) == 1


class TestValidationRepositories:
    async def test_preflight_list_for_session_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        session = await repos.installation_sessions.create(
            InstallationSession(organization_id=organization_id, mode=InstallationMode.CLI)
        )
        await repos.preflight_results.create(
            PreflightResult(
                organization_id=organization_id,
                installation_session_id=session.id,
                check_type=PreflightCheckType.CPU,
                status=CheckResultStatus.PASSED,
                checked_at=utcnow(),
            )
        )
        assert len(await repos.preflight_results.list_for_session(session.id)) == 1
        assert len(await repos.preflight_results.list_recent(organization_id)) == 1

    async def test_dependency_check_list_for_session(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        session = await repos.installation_sessions.create(
            InstallationSession(organization_id=organization_id, mode=InstallationMode.CLI)
        )
        await repos.dependency_checks.create(
            DependencyCheck(
                organization_id=organization_id,
                installation_session_id=session.id,
                dependency_name="postgres",
                required_version="15.0.0",
                found_version="15.2.0",
                status=CheckResultStatus.PASSED,
                checked_at=utcnow(),
            )
        )
        assert len(await repos.dependency_checks.list_for_session(session.id)) == 1


class TestConfigurationRepository:
    async def test_find_by_name_section_and_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.configuration_profiles.create(
            ConfigurationProfile(
                organization_id=organization_id,
                name="db-config",
                section=ConfigurationSection.DATABASE,
            )
        )
        found = await repos.configuration_profiles.find_by_name(organization_id, name="db-config")
        assert found is not None
        by_section = await repos.configuration_profiles.find_by_section(
            organization_id, section=ConfigurationSection.DATABASE
        )
        assert by_section is not None
        assert len(await repos.configuration_profiles.list_all(organization_id)) == 1


class TestSecretsTlsRepositories:
    async def test_certificate_list_all_expiring_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.tls_certificates.create(
            TlsCertificate(
                organization_id=organization_id,
                common_name="aiios.local",
                not_before=hours_ago(1),
                not_after=hours_ago(-24),
                status=TlsCertificateStatus.VALID,
            )
        )
        assert len(await repos.tls_certificates.list_all(organization_id)) == 1
        expiring = await repos.tls_certificates.list_expiring_before(
            organization_id, before=hours_ago(-48)
        )
        assert len(expiring) == 1
        assert organization_id in await repos.tls_certificates.list_organization_ids()

    async def test_secret_find_active_list_for_name_and_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.generated_secrets.create(
            GeneratedSecret(
                organization_id=organization_id,
                secret_name="db-password",
                secret_type=SecretType.CREDENTIAL,
                masked_value="****abcd",
                status=SecretStatus.ACTIVE,
                generated_at=utcnow(),
            )
        )
        found = await repos.generated_secrets.find_active_by_name(
            organization_id, secret_name="db-password"
        )
        assert found is not None
        assert (
            len(
                await repos.generated_secrets.list_for_name(
                    organization_id, secret_name="db-password"
                )
            )
            == 1
        )
        assert len(await repos.generated_secrets.list_all(organization_id)) == 1


class TestUpgradeRollbackRepositories:
    async def test_upgrade_history_list_recent_and_for_job(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="up1",
                target_type=DeploymentTargetType.PUBLIC_CLOUD,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.HELM,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        job = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.UPGRADE,
            )
        )
        await repos.upgrade_history.create(
            UpgradeHistory(
                organization_id=organization_id,
                deployment_job_id=job.id,
                from_version="1.0.0",
                to_version="1.1.0",
            )
        )
        assert len(await repos.upgrade_history.list_recent(organization_id)) == 1
        assert len(await repos.upgrade_history.list_for_job(job.id)) == 1

    async def test_rollback_history_list_recent_and_for_job(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="rb1",
                target_type=DeploymentTargetType.HYBRID_CLOUD,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.HELM,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        job = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.ROLLBACK,
            )
        )
        await repos.rollback_history.create(
            RollbackHistory(
                organization_id=organization_id,
                deployment_job_id=job.id,
                from_version="1.1.0",
                to_version="1.0.0",
            )
        )
        assert len(await repos.rollback_history.list_recent(organization_id)) == 1
        assert len(await repos.rollback_history.list_for_job(job.id)) == 1


class TestVerificationRepository:
    async def test_list_for_job_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="ver1",
                target_type=DeploymentTargetType.AIR_GAPPED,
                installation_mode=InstallationMode.OFFLINE,
                engine=DeploymentEngine.DOCKER_COMPOSE,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        job = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
            )
        )
        await repos.verification_results.create(
            VerificationResult(
                organization_id=organization_id,
                deployment_job_id=job.id,
                check_type=VerificationCheckType.HEALTH,
                status=CheckResultStatus.PASSED,
                verified_at=utcnow(),
            )
        )
        assert len(await repos.verification_results.list_for_job(job.id)) == 1
        assert len(await repos.verification_results.list_recent(organization_id)) == 1


class TestReportingRepositories:
    async def test_statistic_find_window_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = utcnow()
        await repos.statistics.create(
            DeploymentStatistic(
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
            DeploymentReport(
                organization_id=organization_id,
                kind=DeploymentReportKind.DEPLOYMENT,
                report_format=ReportFormat.JSON,
                title="Deploy report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        assert (
            len(
                await repos.reports.list_recent(
                    organization_id, kind=DeploymentReportKind.DEPLOYMENT
                )
            )
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
            DeploymentAudit(
                organization_id=organization_id,
                action=DeploymentAuditAction.ADMINISTRATIVE,
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
