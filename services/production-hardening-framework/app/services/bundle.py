"""The repository bundle every route works through.

One object rather than sixteen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.certificates import CertificateInventoryRepository
from app.repositories.certification import ProductionCertificationRepository
from app.repositories.compliance import ComplianceResultRepository
from app.repositories.hardening_definitions import HardeningProfileRepository
from app.repositories.hardening_execution import HardeningResultRepository, HardeningRunRepository
from app.repositories.readiness import (
    DisasterRecoveryCheckRepository,
    OperationalReadinessRepository,
)
from app.repositories.reporting import (
    HardeningAuditRepository,
    HardeningReportRepository,
    HardeningStatisticRepository,
)
from app.repositories.runtime_protection import RuntimeProtectionEventRepository
from app.repositories.security_findings import SecurityFindingRepository
from app.repositories.supply_chain import SbomCatalogRepository, SignedArtifactRepository
from app.repositories.vulnerabilities import VulnerabilityScanRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    hardening_profiles: HardeningProfileRepository

    hardening_runs: HardeningRunRepository
    hardening_results: HardeningResultRepository

    security_findings: SecurityFindingRepository

    vulnerability_scans: VulnerabilityScanRepository

    sbom_catalog: SbomCatalogRepository
    signed_artifacts: SignedArtifactRepository

    runtime_protection: RuntimeProtectionEventRepository

    compliance_results: ComplianceResultRepository

    production_certifications: ProductionCertificationRepository

    operational_readiness: OperationalReadinessRepository
    disaster_recovery_checks: DisasterRecoveryCheckRepository

    certificate_inventory: CertificateInventoryRepository

    statistics: HardeningStatisticRepository
    reports: HardeningReportRepository
    audit: HardeningAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        hardening_profiles=HardeningProfileRepository(session, tenant_scope=tenant_scope),
        hardening_runs=HardeningRunRepository(session, tenant_scope=tenant_scope),
        hardening_results=HardeningResultRepository(session, tenant_scope=tenant_scope),
        security_findings=SecurityFindingRepository(session, tenant_scope=tenant_scope),
        vulnerability_scans=VulnerabilityScanRepository(session, tenant_scope=tenant_scope),
        sbom_catalog=SbomCatalogRepository(session, tenant_scope=tenant_scope),
        signed_artifacts=SignedArtifactRepository(session, tenant_scope=tenant_scope),
        runtime_protection=RuntimeProtectionEventRepository(session, tenant_scope=tenant_scope),
        compliance_results=ComplianceResultRepository(session, tenant_scope=tenant_scope),
        production_certifications=ProductionCertificationRepository(
            session, tenant_scope=tenant_scope
        ),
        operational_readiness=OperationalReadinessRepository(session, tenant_scope=tenant_scope),
        disaster_recovery_checks=DisasterRecoveryCheckRepository(
            session, tenant_scope=tenant_scope
        ),
        certificate_inventory=CertificateInventoryRepository(session, tenant_scope=tenant_scope),
        statistics=HardeningStatisticRepository(session, tenant_scope=tenant_scope),
        reports=HardeningReportRepository(session, tenant_scope=tenant_scope),
        audit=HardeningAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
