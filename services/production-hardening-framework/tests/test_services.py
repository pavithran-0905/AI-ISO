"""Unit/integration tests for every service, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    CheckResultStatus,
    CisBenchmark,
    ComplianceFramework,
    DisasterRecoveryCheckType,
    FindingSeverity,
    HardeningAuditAction,
    HardeningReportKind,
    HardeningTargetType,
    OperationalReadinessCheckType,
    RuntimeProtectionEventType,
    VulnerabilityScanType,
)
from app.services import hardening_execution as hardening_execution_services
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.certificates import CertificateInventoryService
from app.services.certification import ProductionCertificationService
from app.services.compliance import ComplianceService
from app.services.hardening_definitions import HardeningProfileService
from app.services.hardening_execution import HardeningResultService, HardeningRunService
from app.services.readiness import DisasterRecoveryCheckService, OperationalReadinessService
from app.services.reports import ReportService
from app.services.runtime_protection import RuntimeProtectionService
from app.services.security_findings import SecurityFindingService
from app.services.statistics import StatisticsService
from app.services.supply_chain import SbomCatalogService, SignedArtifactService
from app.services.vulnerabilities import VulnerabilityScanService
from tests.conftest import RecordingNotifier, RecordingPublisher, days_ago, hours_ago, utcnow


async def _make_profile(repos: Repositories, organization_id: uuid.UUID, name: str = "p1"):
    service = HardeningProfileService(repos.hardening_profiles)
    return await service.create(
        organization_id,
        name=name,
        target_type=HardeningTargetType.OS,
        benchmark=CisBenchmark.LINUX_CIS,
    )


class TestHardeningDefinitionsService:
    async def test_profile_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        profile = await _make_profile(repos, organization_id)
        assert profile.name == "p1"


class TestHardeningExecutionServices:
    async def test_run_start_and_complete_succeeded(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="p2")
        service = HardeningRunService(repos.hardening_runs, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        run = await service.create(organization_id, hardening_profile_id=profile.id)
        run = await service.start(run, now=utcnow())
        assert "HardeningStarted" in publisher.names()
        completed = await service.complete(run, status="succeeded", now=utcnow())  # type: ignore[arg-type]
        assert completed.status == "succeeded"
        assert "HardeningCompleted" in publisher.names()
        assert not any(call[0] == "notify_hardening_failed" for call in notifier.calls)

    async def test_run_complete_failed_notifies(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="p3")
        service = HardeningRunService(repos.hardening_runs, notifier=notifier)  # type: ignore[arg-type]
        run = await service.create(organization_id, hardening_profile_id=profile.id)
        run = await service.start(run, now=utcnow())
        completed = await service.complete(
            run, status="failed", now=utcnow(), error_message="boom", hardening_profile_name="p3"  # type: ignore[arg-type]
        )
        assert completed.status == "failed"
        assert any(call[0] == "notify_hardening_failed" for call in notifier.calls)

    async def test_run_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await _make_profile(repos, organization_id, name="p4")
        service = HardeningRunService(repos.hardening_runs)
        run = await service.create(organization_id, hardening_profile_id=profile.id)
        with pytest.raises(hardening_execution_services.TransitionRefusedError):
            await service.complete(run, status="succeeded", now=utcnow())  # type: ignore[arg-type]

    async def test_result_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        profile = await _make_profile(repos, organization_id, name="p5")
        run_service = HardeningRunService(repos.hardening_runs)
        run = await run_service.create(organization_id, hardening_profile_id=profile.id)
        result_service = HardeningResultService(repos.hardening_results)
        result = await result_service.record(
            organization_id,
            hardening_run_id=run.id,
            check_name="cis-1.1.1",
            status=CheckResultStatus.PASSED,
        )
        assert result.status == "passed"


class TestSecurityFindingService:
    async def test_record_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = SecurityFindingService(repos.security_findings, publish=publisher)
        finding = await service.record(
            organization_id,
            target_type=HardeningTargetType.API,
            severity=FindingSeverity.HIGH,
            title="no rate limit",
        )
        assert finding.title == "no rate limit"
        assert "SecurityIssueDetected" in publisher.names()


class TestVulnerabilityScanService:
    async def test_record_publishes_and_list_overdue(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = VulnerabilityScanService(repos.vulnerability_scans, publish=publisher)
        scan = await service.record(
            organization_id,
            scan_type=VulnerabilityScanType.DEPENDENCY,
            severity=FindingSeverity.CRITICAL,
            package_name="left-pad",
            cve_id="CVE-2024-0001",
        )
        assert scan.package_name == "left-pad"
        assert "VulnerabilityDetected" in publisher.names()

        scan.created_at = days_ago(10)
        await repos.vulnerability_scans.update(scan)
        overdue = await service.list_overdue(organization_id, now=utcnow())
        assert any(row.id == scan.id for row in overdue)


class TestSupplyChainServices:
    async def test_sbom_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = SbomCatalogService(repos.sbom_catalog)
        entry = await service.record(
            organization_id,
            component_name="fastapi",
            component_version="0.115.0",
            generated_at=utcnow(),
        )
        assert entry.component_name == "fastapi"

    async def test_signed_artifact_record(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SignedArtifactService(repos.signed_artifacts)
        artifact = await service.record(
            organization_id,
            artifact_name="release.tar.gz",
            signature="deadbeef",
            is_verified=True,
            signed_at=utcnow(),
        )
        assert artifact.is_verified is True


class TestRuntimeProtectionService:
    async def test_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = RuntimeProtectionService(repos.runtime_protection)
        event = await service.record(
            organization_id,
            event_type=RuntimeProtectionEventType.PRIVILEGE_ESCALATION,
            severity=FindingSeverity.CRITICAL,
            detected_at=utcnow(),
        )
        assert event.event_type == "privilege_escalation"


class TestComplianceService:
    async def test_evaluate_compliant_no_notification(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = ComplianceService(repos.compliance_results, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        result = await service.evaluate(
            organization_id,
            framework=ComplianceFramework.SOC2,
            control_id="CC6.1",
            is_compliant=True,
            evaluated_at=utcnow(),
        )
        assert result.is_compliant is True
        assert "ComplianceValidated" in publisher.names()
        assert notifier.calls == []

    async def test_evaluate_non_compliant_notifies(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = ComplianceService(repos.compliance_results, notifier=notifier)  # type: ignore[arg-type]
        result = await service.evaluate(
            organization_id,
            framework=ComplianceFramework.PCI_DSS,
            control_id="3.4",
            is_compliant=False,
            evaluated_at=utcnow(),
        )
        assert result.is_compliant is False
        assert any(call[0] == "notify_compliance_failure" for call in notifier.calls)


class TestProductionCertificationService:
    async def test_evaluate_and_create_grants_when_low_risk(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = ProductionCertificationService(  # type: ignore[arg-type]
            repos.production_certifications, publish=publisher, notifier=notifier
        )
        certification = await service.evaluate_and_create(
            organization_id,
            name="core-platform",
            hardening_rate=1.0,
            compliance_rate=1.0,
            readiness_rate=1.0,
            risk_threshold=50.0,
            now=utcnow(),
        )
        assert certification.status == "granted"
        assert "CertificationGranted" in publisher.names()
        assert any(call[0] == "notify_certification_granted" for call in notifier.calls)

    async def test_evaluate_and_create_pending_when_high_risk(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = ProductionCertificationService(repos.production_certifications, publish=publisher)
        certification = await service.evaluate_and_create(
            organization_id,
            name="risky-service",
            hardening_rate=0.0,
            compliance_rate=0.0,
            readiness_rate=0.0,
            risk_threshold=50.0,
            now=utcnow(),
        )
        assert certification.status == "pending"
        assert "CertificationGranted" not in publisher.names()

    async def test_revoke(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = ProductionCertificationService(repos.production_certifications, publish=publisher)
        certification = await service.evaluate_and_create(
            organization_id,
            name="to-revoke",
            hardening_rate=1.0,
            compliance_rate=1.0,
            readiness_rate=1.0,
            risk_threshold=50.0,
            now=utcnow(),
        )
        revoked = await service.revoke(certification, reason="failed re-hardening")
        assert revoked.status == "revoked"
        assert "CertificationRevoked" in publisher.names()


class TestReadinessServices:
    async def test_operational_readiness_notifies_on_failure(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = OperationalReadinessService(repos.operational_readiness, notifier=notifier)  # type: ignore[arg-type]
        check = await service.record(
            organization_id,
            check_type=OperationalReadinessCheckType.MONITORING,
            status=CheckResultStatus.FAILED,
            detail="no alert configured",
            checked_at=utcnow(),
        )
        assert check.status == "failed"
        assert any(call[0] == "notify_operational_risk" for call in notifier.calls)

    async def test_operational_readiness_no_notification_on_pass(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = OperationalReadinessService(repos.operational_readiness, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id,
            check_type=OperationalReadinessCheckType.MONITORING,
            status=CheckResultStatus.PASSED,
            checked_at=utcnow(),
        )
        assert notifier.calls == []

    async def test_disaster_recovery_check_record(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = DisasterRecoveryCheckService(repos.disaster_recovery_checks)
        check = await service.record(
            organization_id,
            check_type=DisasterRecoveryCheckType.BACKUP_VALIDATION,
            status=CheckResultStatus.PASSED,
            checked_at=utcnow(),
        )
        assert check.status == "passed"


class TestCertificateInventoryService:
    async def test_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = CertificateInventoryService(repos.certificate_inventory)
        entry = await service.record(
            organization_id, subject="api.example.com", expires_at=utcnow()
        )
        assert entry.subject == "api.example.com"


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
            hardening_run_count=1,
            security_finding_count=0,
            vulnerability_count=0,
            avg_hardening_score=0.9,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            hardening_run_count=5,
            security_finding_count=2,
            vulnerability_count=1,
            avg_hardening_score=0.8,
        )
        assert first.id == second.id
        assert second.hardening_run_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=HardeningReportKind.HARDENING,
            title="Weekly hardening report",
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
            action=HardeningAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"
