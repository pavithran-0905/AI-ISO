"""The repository bundle every route works through.

One object rather than twenty constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.accounts import (
    CloudAccountRepository,
    CloudProjectRepository,
    CloudProviderRepository,
    CloudRegionRepository,
)
from app.repositories.operations import (
    CloudBudgetRepository,
    CloudCatalogRepository,
    CloudComplianceRepository,
    CloudCostRepository,
    CloudDriftRepository,
    CloudIaCRepository,
    CloudPolicyRepository,
)
from app.repositories.reporting import (
    CloudAuditRepository,
    CloudReportRepository,
    CloudStatisticRepository,
)
from app.repositories.resources import (
    CloudComputeRepository,
    CloudDatabaseRepository,
    CloudKubernetesRepository,
    CloudNetworkRepository,
    CloudResourceRepository,
    CloudStorageRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    providers: CloudProviderRepository
    accounts: CloudAccountRepository
    regions: CloudRegionRepository
    projects: CloudProjectRepository

    resources: CloudResourceRepository
    compute: CloudComputeRepository
    storage: CloudStorageRepository
    networks: CloudNetworkRepository
    databases: CloudDatabaseRepository
    kubernetes: CloudKubernetesRepository

    costs: CloudCostRepository
    budgets: CloudBudgetRepository
    policies: CloudPolicyRepository
    compliance: CloudComplianceRepository
    drift: CloudDriftRepository
    iac: CloudIaCRepository
    catalog: CloudCatalogRepository

    statistics: CloudStatisticRepository
    reports: CloudReportRepository
    audit: CloudAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        providers=CloudProviderRepository(session, tenant_scope=tenant_scope),
        accounts=CloudAccountRepository(session, tenant_scope=tenant_scope),
        regions=CloudRegionRepository(session, tenant_scope=tenant_scope),
        projects=CloudProjectRepository(session, tenant_scope=tenant_scope),
        resources=CloudResourceRepository(session, tenant_scope=tenant_scope),
        compute=CloudComputeRepository(session, tenant_scope=tenant_scope),
        storage=CloudStorageRepository(session, tenant_scope=tenant_scope),
        networks=CloudNetworkRepository(session, tenant_scope=tenant_scope),
        databases=CloudDatabaseRepository(session, tenant_scope=tenant_scope),
        kubernetes=CloudKubernetesRepository(session, tenant_scope=tenant_scope),
        costs=CloudCostRepository(session, tenant_scope=tenant_scope),
        budgets=CloudBudgetRepository(session, tenant_scope=tenant_scope),
        policies=CloudPolicyRepository(session, tenant_scope=tenant_scope),
        compliance=CloudComplianceRepository(session, tenant_scope=tenant_scope),
        drift=CloudDriftRepository(session, tenant_scope=tenant_scope),
        iac=CloudIaCRepository(session, tenant_scope=tenant_scope),
        catalog=CloudCatalogRepository(session, tenant_scope=tenant_scope),
        statistics=CloudStatisticRepository(session, tenant_scope=tenant_scope),
        reports=CloudReportRepository(session, tenant_scope=tenant_scope),
        audit=CloudAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
