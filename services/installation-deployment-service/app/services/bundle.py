"""The repository bundle every route works through.

One object rather than twenty-one constructor arguments, all sharing
one tenant scope: a bundle where one repository was built without it
would enforce tenant isolation everywhere except the one query that
forgot, and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.configuration import ConfigurationProfileRepository
from app.repositories.deployment import (
    DeploymentArtifactRepository,
    DeploymentHistoryRepository,
    DeploymentInventoryRepository,
    DeploymentJobRepository,
    DeploymentProfileRepository,
    DeploymentStatusRepository,
    DeploymentTargetRepository,
    DeploymentVersionRepository,
)
from app.repositories.installation import InstallationLogRepository, InstallationSessionRepository
from app.repositories.reporting import (
    DeploymentAuditRepository,
    DeploymentReportRepository,
    DeploymentStatisticRepository,
)
from app.repositories.secrets_tls import GeneratedSecretRepository, TlsCertificateRepository
from app.repositories.upgrade_rollback import RollbackHistoryRepository, UpgradeHistoryRepository
from app.repositories.validation import DependencyCheckRepository, PreflightResultRepository
from app.repositories.verification import VerificationResultRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    profiles: DeploymentProfileRepository
    targets: DeploymentTargetRepository
    inventory: DeploymentInventoryRepository
    jobs: DeploymentJobRepository
    history: DeploymentHistoryRepository
    versions: DeploymentVersionRepository
    artifacts: DeploymentArtifactRepository
    status_board: DeploymentStatusRepository

    installation_sessions: InstallationSessionRepository
    installation_logs: InstallationLogRepository

    preflight_results: PreflightResultRepository
    dependency_checks: DependencyCheckRepository

    configuration_profiles: ConfigurationProfileRepository

    tls_certificates: TlsCertificateRepository
    generated_secrets: GeneratedSecretRepository

    upgrade_history: UpgradeHistoryRepository
    rollback_history: RollbackHistoryRepository

    verification_results: VerificationResultRepository

    statistics: DeploymentStatisticRepository
    reports: DeploymentReportRepository
    audit: DeploymentAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        profiles=DeploymentProfileRepository(session, tenant_scope=tenant_scope),
        targets=DeploymentTargetRepository(session, tenant_scope=tenant_scope),
        inventory=DeploymentInventoryRepository(session, tenant_scope=tenant_scope),
        jobs=DeploymentJobRepository(session, tenant_scope=tenant_scope),
        history=DeploymentHistoryRepository(session, tenant_scope=tenant_scope),
        versions=DeploymentVersionRepository(session, tenant_scope=tenant_scope),
        artifacts=DeploymentArtifactRepository(session, tenant_scope=tenant_scope),
        status_board=DeploymentStatusRepository(session, tenant_scope=tenant_scope),
        installation_sessions=InstallationSessionRepository(session, tenant_scope=tenant_scope),
        installation_logs=InstallationLogRepository(session, tenant_scope=tenant_scope),
        preflight_results=PreflightResultRepository(session, tenant_scope=tenant_scope),
        dependency_checks=DependencyCheckRepository(session, tenant_scope=tenant_scope),
        configuration_profiles=ConfigurationProfileRepository(session, tenant_scope=tenant_scope),
        tls_certificates=TlsCertificateRepository(session, tenant_scope=tenant_scope),
        generated_secrets=GeneratedSecretRepository(session, tenant_scope=tenant_scope),
        upgrade_history=UpgradeHistoryRepository(session, tenant_scope=tenant_scope),
        rollback_history=RollbackHistoryRepository(session, tenant_scope=tenant_scope),
        verification_results=VerificationResultRepository(session, tenant_scope=tenant_scope),
        statistics=DeploymentStatisticRepository(session, tenant_scope=tenant_scope),
        reports=DeploymentReportRepository(session, tenant_scope=tenant_scope),
        audit=DeploymentAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
