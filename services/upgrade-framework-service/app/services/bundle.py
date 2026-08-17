"""The repository bundle every route works through.

One object rather than seventeen constructor arguments, all sharing
one tenant scope: a bundle where one repository was built without it
would enforce tenant isolation everywhere except the one query that
forgot, and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.compatibility import CompatibilityMatrixRepository
from app.repositories.migrations import (
    ConfigurationMigrationRepository,
    MigrationHistoryRepository,
    PluginMigrationRepository,
)
from app.repositories.releases import ReleaseChannelRepository, ReleaseVersionRepository
from app.repositories.reporting import (
    UpgradeAuditRepository,
    UpgradeReportRepository,
    UpgradeStatisticRepository,
)
from app.repositories.rollback import RollbackHistoryRepository
from app.repositories.upgrade import (
    UpgradeDependencyRepository,
    UpgradeHistoryRepository,
    UpgradeJobRepository,
    UpgradePlanRepository,
    UpgradeResultRepository,
    UpgradeTargetRepository,
)
from app.repositories.verification import VerificationResultRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    channels: ReleaseChannelRepository
    versions: ReleaseVersionRepository

    plans: UpgradePlanRepository
    jobs: UpgradeJobRepository
    history: UpgradeHistoryRepository
    targets: UpgradeTargetRepository
    results: UpgradeResultRepository
    dependencies: UpgradeDependencyRepository

    compatibility: CompatibilityMatrixRepository

    migration_history: MigrationHistoryRepository
    configuration_migrations: ConfigurationMigrationRepository
    plugin_migrations: PluginMigrationRepository

    rollback_history: RollbackHistoryRepository

    verification_results: VerificationResultRepository

    statistics: UpgradeStatisticRepository
    reports: UpgradeReportRepository
    audit: UpgradeAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        channels=ReleaseChannelRepository(session, tenant_scope=tenant_scope),
        versions=ReleaseVersionRepository(session, tenant_scope=tenant_scope),
        plans=UpgradePlanRepository(session, tenant_scope=tenant_scope),
        jobs=UpgradeJobRepository(session, tenant_scope=tenant_scope),
        history=UpgradeHistoryRepository(session, tenant_scope=tenant_scope),
        targets=UpgradeTargetRepository(session, tenant_scope=tenant_scope),
        results=UpgradeResultRepository(session, tenant_scope=tenant_scope),
        dependencies=UpgradeDependencyRepository(session, tenant_scope=tenant_scope),
        compatibility=CompatibilityMatrixRepository(session, tenant_scope=tenant_scope),
        migration_history=MigrationHistoryRepository(session, tenant_scope=tenant_scope),
        configuration_migrations=ConfigurationMigrationRepository(
            session, tenant_scope=tenant_scope
        ),
        plugin_migrations=PluginMigrationRepository(session, tenant_scope=tenant_scope),
        rollback_history=RollbackHistoryRepository(session, tenant_scope=tenant_scope),
        verification_results=VerificationResultRepository(session, tenant_scope=tenant_scope),
        statistics=UpgradeStatisticRepository(session, tenant_scope=tenant_scope),
        reports=UpgradeReportRepository(session, tenant_scope=tenant_scope),
        audit=UpgradeAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
