"""Repository tests, against real PostgreSQL, exercising every custom
method (not the generic CRUD ``BaseRepository`` already provides)."""

from __future__ import annotations

import uuid

from app.models.certificates import CertificateInventoryEntry
from app.models.certification import ProductionCertification
from app.models.compliance import ComplianceResult
from app.models.enums import (
    CertificationStatus,
    CheckResultStatus,
    CisBenchmark,
    ComplianceFramework,
    DisasterRecoveryCheckType,
    FindingSeverity,
    FindingStatus,
    HardeningAuditAction,
    HardeningReportKind,
    HardeningRunStatus,
    HardeningTargetType,
    OperationalReadinessCheckType,
    ReportStatus,
    RuntimeProtectionEventType,
    VulnerabilityScanType,
)
from app.models.hardening_definitions import HardeningProfile
from app.models.hardening_execution import HardeningResult, HardeningRun
from app.models.readiness import DisasterRecoveryCheck, OperationalReadiness
from app.models.reporting import HardeningAudit, HardeningReport, HardeningStatistic
from app.models.runtime_protection import RuntimeProtectionEvent
from app.models.security_findings import SecurityFinding
from app.models.supply_chain import SbomCatalog, SignedArtifact
from app.models.vulnerabilities import VulnerabilityScan
from app.services.bundle import Repositories
from tests.conftest import hours_ago, utcnow


class TestHardeningDefinitionsRepository:
    async def test_list_all(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="linux-cis",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        rows = await repos.hardening_profiles.list_all(organization_id)
        assert len(rows) == 1


class TestHardeningExecutionRepositories:
    async def test_run_list_recent_and_running(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="docker-cis",
                target_type=HardeningTargetType.CONTAINER,
                benchmark=CisBenchmark.DOCKER_CIS,
            )
        )
        await repos.hardening_runs.create(
            HardeningRun(
                organization_id=organization_id,
                hardening_profile_id=profile.id,
                status=HardeningRunStatus.RUNNING,
            )
        )
        recent = await repos.hardening_runs.list_recent(organization_id)
        assert len(recent) == 1
        running = await repos.hardening_runs.list_running(organization_id)
        assert len(running) == 1
        org_ids = await repos.hardening_runs.list_organization_ids()
        assert organization_id in org_ids

    async def test_result_list_for_run_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="k8s-cis",
                target_type=HardeningTargetType.KUBERNETES,
                benchmark=CisBenchmark.KUBERNETES_CIS,
            )
        )
        run = await repos.hardening_runs.create(
            HardeningRun(organization_id=organization_id, hardening_profile_id=profile.id)
        )
        await repos.hardening_results.create(
            HardeningResult(
                organization_id=organization_id,
                hardening_run_id=run.id,
                check_name="cis-1.1.1",
                status=CheckResultStatus.PASSED,
            )
        )
        for_run = await repos.hardening_results.list_for_run(run.id)
        assert len(for_run) == 1
        recent = await repos.hardening_results.list_recent(organization_id)
        assert len(recent) == 1


class TestSecurityFindingsRepository:
    async def test_list_all_and_by_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.security_findings.create(
            SecurityFinding(
                organization_id=organization_id,
                target_type=HardeningTargetType.API,
                severity=FindingSeverity.HIGH,
                title="missing rate limiting",
            )
        )
        rows = await repos.security_findings.list_all(organization_id)
        assert len(rows) == 1
        open_findings = await repos.security_findings.list_by_status(
            organization_id, status=FindingStatus.OPEN
        )
        assert len(open_findings) == 1
        org_ids = await repos.security_findings.list_organization_ids()
        assert organization_id in org_ids


class TestVulnerabilitiesRepository:
    async def test_list_all_open_and_org_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.vulnerability_scans.create(
            VulnerabilityScan(
                organization_id=organization_id,
                scan_type=VulnerabilityScanType.DEPENDENCY,
                severity=FindingSeverity.CRITICAL,
                package_name="left-pad",
            )
        )
        rows = await repos.vulnerability_scans.list_all(organization_id)
        assert len(rows) == 1
        open_scans = await repos.vulnerability_scans.list_open(organization_id)
        assert len(open_scans) == 1
        org_ids = await repos.vulnerability_scans.list_organization_ids()
        assert organization_id in org_ids


class TestSupplyChainRepositories:
    async def test_sbom_and_signed_artifact_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.sbom_catalog.create(
            SbomCatalog(
                organization_id=organization_id,
                component_name="fastapi",
                component_version="0.115.0",
                generated_at=utcnow(),
            )
        )
        await repos.signed_artifacts.create(
            SignedArtifact(
                organization_id=organization_id,
                artifact_name="release.tar.gz",
                signature="deadbeef",
                signed_at=utcnow(),
            )
        )
        sbom_rows = await repos.sbom_catalog.list_all(organization_id)
        assert len(sbom_rows) == 1
        artifact_rows = await repos.signed_artifacts.list_all(organization_id)
        assert len(artifact_rows) == 1


class TestRuntimeProtectionRepository:
    async def test_list_all(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await repos.runtime_protection.create(
            RuntimeProtectionEvent(
                organization_id=organization_id,
                event_type=RuntimeProtectionEventType.ANOMALY,
                severity=FindingSeverity.MEDIUM,
                detected_at=utcnow(),
            )
        )
        rows = await repos.runtime_protection.list_all(organization_id)
        assert len(rows) == 1


class TestComplianceRepository:
    async def test_list_all_and_by_framework(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.compliance_results.create(
            ComplianceResult(
                organization_id=organization_id,
                framework=ComplianceFramework.SOC2,
                control_id="CC6.1",
                is_compliant=True,
                evaluated_at=utcnow(),
            )
        )
        rows = await repos.compliance_results.list_all(organization_id)
        assert len(rows) == 1
        by_framework = await repos.compliance_results.list_by_framework(
            organization_id, framework=ComplianceFramework.SOC2
        )
        assert len(by_framework) == 1
        org_ids = await repos.compliance_results.list_organization_ids()
        assert organization_id in org_ids


class TestCertificationRepository:
    async def test_list_all_and_by_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.production_certifications.create(
            ProductionCertification(
                organization_id=organization_id,
                name="core-platform",
                status=CertificationStatus.GRANTED,
            )
        )
        rows = await repos.production_certifications.list_all(organization_id)
        assert len(rows) == 1
        granted = await repos.production_certifications.list_by_status(
            organization_id, status=CertificationStatus.GRANTED
        )
        assert len(granted) == 1
        org_ids = await repos.production_certifications.list_organization_ids()
        assert organization_id in org_ids


class TestReadinessRepositories:
    async def test_operational_and_dr_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.operational_readiness.create(
            OperationalReadiness(
                organization_id=organization_id,
                check_type=OperationalReadinessCheckType.MONITORING,
                status=CheckResultStatus.PASSED,
                checked_at=utcnow(),
            )
        )
        await repos.disaster_recovery_checks.create(
            DisasterRecoveryCheck(
                organization_id=organization_id,
                check_type=DisasterRecoveryCheckType.BACKUP_VALIDATION,
                status=CheckResultStatus.PASSED,
                checked_at=utcnow(),
            )
        )
        operational_rows = await repos.operational_readiness.list_all(organization_id)
        assert len(operational_rows) == 1
        dr_rows = await repos.disaster_recovery_checks.list_all(organization_id)
        assert len(dr_rows) == 1


class TestCertificatesRepository:
    async def test_list_all_valid_and_org_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.certificate_inventory.create(
            CertificateInventoryEntry(
                organization_id=organization_id,
                subject="api.example.com",
                expires_at=hours_ago(-24),
            )
        )
        rows = await repos.certificate_inventory.list_all(organization_id)
        assert len(rows) == 1
        valid_rows = await repos.certificate_inventory.list_valid(organization_id)
        assert len(valid_rows) == 1
        org_ids = await repos.certificate_inventory.list_organization_ids()
        assert organization_id in org_ids


class TestReportingRepositories:
    async def test_statistic_find_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = hours_ago(1)
        await repos.statistics.create(
            HardeningStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=utcnow(),
                hardening_run_count=5,
                security_finding_count=1,
                vulnerability_count=0,
                avg_hardening_score=0.9,
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        rows = await repos.statistics.list_range(organization_id, since=hours_ago(2))
        assert len(rows) == 1

    async def test_report_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            HardeningReport(
                organization_id=organization_id,
                kind=HardeningReportKind.HARDENING,
                title="Weekly hardening report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        rows = await repos.reports.list_recent(organization_id)
        assert len(rows) == 1
        by_kind = await repos.reports.list_recent(
            organization_id, kind=HardeningReportKind.HARDENING
        )
        assert len(by_kind) == 1

    async def test_audit_list_recent_and_for_entity(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            HardeningAudit(
                organization_id=organization_id,
                action=HardeningAuditAction.HARDENING_RUN,
                entity_type="hardening_run",
                entity_id=entity_id,
                summary="ran a hardening profile",
                occurred_at=utcnow(),
            )
        )
        rows = await repos.audit.list_recent(organization_id)
        assert len(rows) == 1
        for_entity = await repos.audit.list_for_entity("hardening_run", entity_id)
        assert len(for_entity) == 1
