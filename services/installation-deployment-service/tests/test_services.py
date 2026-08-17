"""Unit/integration tests for every service, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

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
    SecretType,
    VerificationCheckType,
)
from app.services import deployment as deployment_services
from app.services import installer as installer_services
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.configuration import ConfigurationProfileService
from app.services.dependencies import DependencyCheckService
from app.services.deployment import (
    DeploymentArtifactService,
    DeploymentJobService,
    DeploymentProfileService,
    DeploymentStatusService,
    DeploymentTargetService,
    DeploymentVersionService,
)
from app.services.installer import InstallationLogService, InstallationSessionService
from app.services.preflight import PreflightService
from app.services.reports import ReportService
from app.services.rollback import InvalidRollbackTargetError, RollbackService
from app.services.secrets_service import SecretsService
from app.services.statistics import StatisticsService
from app.services.tls import TlsCertificateService
from app.services.upgrade import InvalidUpgradePathError, UpgradeService
from app.services.verification import VerificationService
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


async def _make_profile(repos: Repositories, organization_id: uuid.UUID, name: str = "p1"):
    service = DeploymentProfileService(repos.profiles)
    return await service.create(
        organization_id,
        name=name,
        target_type=DeploymentTargetType.DOCKER_COMPOSE,
        installation_mode=InstallationMode.CLI,
        engine=DeploymentEngine.DOCKER_COMPOSE,
        strategy=DeploymentStrategy.ROLLING,
    )


class TestInstallerServices:
    async def test_session_start_publishes_and_complete_notifies_on_failure(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = InstallationSessionService(
            repos.installation_sessions, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        session = await service.create(organization_id, mode=InstallationMode.CLI, actor_id="u1")
        started = await service.start(session, now=utcnow())
        assert "InstallationStarted" in publisher.names()
        completed = await service.complete(
            started, status=InstallationSessionStatus.FAILED, now=utcnow(), reason="disk full"
        )
        assert completed.status == "failed"
        assert "InstallationCompleted" in publisher.names()
        assert ("notify_installation_failed", {"reason": "disk full"}) in notifier.calls

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = InstallationSessionService(repos.installation_sessions)
        session = await service.create(organization_id, mode=InstallationMode.CLI)
        with pytest.raises(installer_services.TransitionRefusedError):
            await service.complete(
                session, status=InstallationSessionStatus.SUCCEEDED, now=utcnow()
            )

    async def test_log_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        session_service = InstallationSessionService(repos.installation_sessions)
        session = await session_service.create(organization_id, mode=InstallationMode.CLI)
        log_service = InstallationLogService(repos.installation_logs)
        log = await log_service.record(
            organization_id,
            installation_session_id=session.id,
            level="info",
            message="hi",
            now=utcnow(),
        )
        assert log.message == "hi"


class TestPreflightService:
    async def test_record_result_publishes_and_notifies_on_failure(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = PreflightService(repos.preflight_results, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        await service.record_result(
            organization_id,
            check_type=PreflightCheckType.CPU,
            status=CheckResultStatus.FAILED,
            detail="low cpu",
            now=utcnow(),
        )
        assert "ValidationCompleted" in publisher.names()
        assert (
            "notify_validation_failed",
            {"check_type": "cpu", "detail": "low cpu"},
        ) in notifier.calls

    async def test_compute_overall_aggregates(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = PreflightService(repos.preflight_results)
        session_service = InstallationSessionService(repos.installation_sessions)
        session = await session_service.create(organization_id, mode=InstallationMode.CLI)
        await service.record_result(
            organization_id,
            check_type=PreflightCheckType.CPU,
            status=CheckResultStatus.PASSED,
            installation_session_id=session.id,
            now=utcnow(),
        )
        await service.record_result(
            organization_id,
            check_type=PreflightCheckType.MEMORY,
            status=CheckResultStatus.WARNING,
            installation_session_id=session.id,
            now=utcnow(),
        )
        overall = await service.compute_overall(session.id)
        assert overall == CheckResultStatus.WARNING


class TestDependencyCheckService:
    async def test_check_classifies_and_records(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = DependencyCheckService(repos.dependency_checks)
        result = await service.check(
            organization_id,
            dependency_name="postgres",
            required_version="15.0.0",
            found_version="14.0.0",
            now=utcnow(),
        )
        assert result.status == "failed"


class TestDeploymentServices:
    async def test_profile_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        profile = await _make_profile(repos, organization_id)
        assert profile.name == "p1"

    async def test_target_register_and_mark_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.models.enums import InventoryNodeStatus

        profile = await _make_profile(repos, organization_id, name="p2")
        service = DeploymentTargetService(repos.targets)
        target = await service.register(
            organization_id,
            deployment_profile_id=profile.id,
            name="t1",
            target_type=DeploymentTargetType.DOCKER_COMPOSE,
        )
        updated = await service.mark_status(target, status=InventoryNodeStatus.ONLINE)
        assert updated.status == "online"

    async def test_job_start_and_complete_notifies_on_failure(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="p3")
        service = DeploymentJobService(
            repos.jobs, repos.history, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        job = await service.create(
            organization_id, deployment_profile_id=profile.id, job_type=DeploymentJobType.DEPLOY
        )
        job = await service.start(job, now=utcnow())
        assert "DeploymentStarted" in publisher.names()
        assert len(await repos.history.list_for_job(job.id)) == 1
        job = await service.complete(
            job, status=DeploymentJobStatus.FAILED, now=utcnow(), error_message="boom"
        )
        assert "DeploymentCompleted" in publisher.names()
        assert (
            "notify_deployment_failed",
            {"job_type": "deploy", "reason": "boom"},
        ) in notifier.calls
        assert len(await repos.history.list_for_job(job.id)) == 2

    async def test_job_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="p4")
        service = DeploymentJobService(repos.jobs, repos.history)
        job = await service.create(
            organization_id, deployment_profile_id=profile.id, job_type=DeploymentJobType.DEPLOY
        )
        with pytest.raises(deployment_services.TransitionRefusedError):
            await service.complete(job, status=DeploymentJobStatus.SUCCEEDED, now=utcnow())

    async def test_status_board_upserts(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="p5")
        target_service = DeploymentTargetService(repos.targets)
        target = await target_service.register(
            organization_id,
            deployment_profile_id=profile.id,
            name="t5",
            target_type=DeploymentTargetType.DOCKER_COMPOSE,
        )
        service = DeploymentStatusService(repos.status_board)
        first = await service.record(
            organization_id,
            deployment_target_id=target.id,
            status=DeploymentJobStatus.RUNNING,
            now=utcnow(),
        )
        second = await service.record(
            organization_id,
            deployment_target_id=target.id,
            status=DeploymentJobStatus.SUCCEEDED,
            now=utcnow(),
        )
        assert first.id == second.id
        assert second.status == "succeeded"

    async def test_version_register_and_mark_current(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = DeploymentVersionService(repos.versions)
        first = await service.register(
            organization_id, version_label="1.0.0", released_at=hours_ago(2)
        )
        second = await service.register(
            organization_id, version_label="1.1.0", released_at=hours_ago(1)
        )
        await service.mark_current(first)
        marked = await service.mark_current(second)
        assert marked.is_current is True
        refreshed_first = await repos.versions.find_by_label(organization_id, version_label="1.0.0")
        assert refreshed_first is not None
        assert refreshed_first.is_current is False

    async def test_artifact_register(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        version_service = DeploymentVersionService(repos.versions)
        version = await version_service.register(
            organization_id, version_label="2.0.0", released_at=utcnow()
        )
        service = DeploymentArtifactService(repos.artifacts)
        artifact = await service.register(
            organization_id,
            deployment_version_id=version.id,
            artifact_type="container_image",
            checksum_sha256="a" * 64,
        )
        assert artifact.artifact_type == "container_image"


class TestUpgradeService:
    async def test_initiate_rejects_invalid_path(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="up1")
        job_service = DeploymentJobService(repos.jobs, repos.history)
        service = UpgradeService(repos.upgrade_history, job_service)
        with pytest.raises(InvalidUpgradePathError):
            await service.initiate(
                organization_id,
                deployment_profile_id=profile.id,
                from_version="2.0.0",
                to_version="1.0.0",
                now=utcnow(),
            )

    async def test_initiate_and_complete_lifecycle(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="up2")
        job_service = DeploymentJobService(repos.jobs, repos.history, publish=publisher)
        service = UpgradeService(
            repos.upgrade_history, job_service, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        history = await service.initiate(
            organization_id,
            deployment_profile_id=profile.id,
            from_version="1.0.0",
            to_version="1.1.0",
            now=utcnow(),
        )
        assert "UpgradeStarted" in publisher.names()
        job = await repos.jobs.require_by_id(history.deployment_job_id)
        completed = await service.complete(
            history,
            job,
            status=DeploymentJobStatus.FAILED,
            now=utcnow(),
            error_message="migration failed",
        )
        assert completed.status == "failed"
        assert "UpgradeCompleted" in publisher.names()
        assert (
            "notify_upgrade_failed",
            {"to_version": "1.1.0", "reason": "migration failed"},
        ) in notifier.calls


class TestRollbackService:
    async def test_initiate_rejects_unknown_target(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="rb1")
        job_service = DeploymentJobService(repos.jobs, repos.history)
        service = RollbackService(repos.rollback_history, job_service)
        with pytest.raises(InvalidRollbackTargetError):
            await service.initiate(
                organization_id,
                deployment_profile_id=profile.id,
                current_version="2.0.0",
                target_version="1.0.0",
                available_versions=["2.0.0"],
                now=utcnow(),
            )

    async def test_initiate_and_complete_fans_notification(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        from app.services.notifications import NotifyingPublisher

        profile = await _make_profile(repos, organization_id, name="rb2")
        job_service = DeploymentJobService(repos.jobs, repos.history)
        wrapped_publish = NotifyingPublisher(publisher, notifier)  # type: ignore[arg-type]
        service = RollbackService(repos.rollback_history, job_service, publish=wrapped_publish)
        history = await service.initiate(
            organization_id,
            deployment_profile_id=profile.id,
            current_version="2.0.0",
            target_version="1.0.0",
            available_versions=["1.0.0", "2.0.0"],
            reason="bad release",
            now=utcnow(),
        )
        assert "RollbackStarted" in publisher.names()
        job = await repos.jobs.require_by_id(history.deployment_job_id)
        completed = await service.complete(
            history, job, status=DeploymentJobStatus.SUCCEEDED, now=utcnow()
        )
        assert completed.status == "succeeded"
        assert "RollbackCompleted" in publisher.names()
        assert any(call[0] == "notify_rollback_completed" for call in notifier.calls)


class TestVerificationService:
    async def test_record_result_and_compute_overall(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="ver1")
        job_service = DeploymentJobService(repos.jobs, repos.history)
        job = await job_service.create(
            organization_id, deployment_profile_id=profile.id, job_type=DeploymentJobType.DEPLOY
        )
        service = VerificationService(repos.verification_results, notifier=notifier)  # type: ignore[arg-type]
        await service.record_result(
            organization_id,
            check_type=VerificationCheckType.HEALTH,
            status=CheckResultStatus.PASSED,
            deployment_job_id=job.id,
            now=utcnow(),
        )
        await service.record_result(
            organization_id,
            check_type=VerificationCheckType.API,
            status=CheckResultStatus.FAILED,
            deployment_job_id=job.id,
            now=utcnow(),
        )
        overall = await service.compute_overall(job.id)
        assert overall == CheckResultStatus.FAILED
        assert any(call[0] == "notify_validation_failed" for call in notifier.calls)


class TestConfigurationProfileService:
    async def test_save_is_idempotent_upsert(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = ConfigurationProfileService(repos.configuration_profiles)
        first = await service.save(
            organization_id, name="db", section=ConfigurationSection.DATABASE, config={"host": "a"}
        )
        second = await service.save(
            organization_id, name="db", section=ConfigurationSection.DATABASE, config={"host": "b"}
        )
        assert first.id == second.id
        assert second.config == {"host": "b"}


class TestSecretsService:
    async def test_generate_returns_raw_value_but_stores_masked(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SecretsService(repos.generated_secrets)
        issued = await service.generate(
            organization_id,
            secret_name="db-password",
            secret_type=SecretType.CREDENTIAL,
            now=utcnow(),
        )
        assert issued.raw_value != issued.record.masked_value
        assert len(issued.raw_value) > 10

    async def test_rotate_retires_old_row_and_issues_new_active_one(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SecretsService(repos.generated_secrets)
        first = await service.generate(
            organization_id, secret_name="api-key", secret_type=SecretType.CREDENTIAL, now=utcnow()
        )
        second = await service.rotate(first.record, now=utcnow())
        assert second.record.id != first.record.id
        assert second.raw_value != first.raw_value
        rows = await repos.generated_secrets.list_for_name(organization_id, secret_name="api-key")
        assert len(rows) == 2
        active = await repos.generated_secrets.find_active_by_name(
            organization_id, secret_name="api-key"
        )
        assert active is not None
        assert active.id == second.record.id


class TestTlsCertificateService:
    async def test_issue_self_signed_returns_private_key_once(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = TlsCertificateService(repos.tls_certificates)
        issued = await service.issue_self_signed(
            organization_id, common_name="aiios.local", valid_days=30
        )
        assert issued.private_key_pem.startswith("-----BEGIN PRIVATE KEY-----")
        assert issued.record.certificate_pem.startswith("-----BEGIN CERTIFICATE-----")

    async def test_refresh_status_updates_on_change_only(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = TlsCertificateService(repos.tls_certificates)
        issued = await service.issue_self_signed(
            organization_id, common_name="aiios.local", valid_days=5
        )
        refreshed = await service.refresh_status(issued.record, now=utcnow(), warning_days=30)
        assert refreshed.status == "expiring"


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
            installation_count=1,
            deployment_count=0,
            upgrade_count=0,
            rollback_count=0,
            validation_failure_count=0,
            success_count=0,
            failure_count=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            installation_count=5,
            deployment_count=0,
            upgrade_count=0,
            rollback_count=0,
            validation_failure_count=0,
            success_count=0,
            failure_count=0,
        )
        assert first.id == second.id
        assert second.installation_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=DeploymentReportKind.DEPLOYMENT,
            title="Deploy report",
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
            action=DeploymentAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"
