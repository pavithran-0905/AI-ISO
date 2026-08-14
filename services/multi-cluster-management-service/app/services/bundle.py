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

from app.repositories.fleet import (
    ClusterCredentialRepository,
    ClusterGroupRepository,
    ClusterRegionRepository,
    ClusterRepository,
    ClusterVersionRepository,
)
from app.repositories.operations import (
    ClusterCapacityRepository,
    ClusterComplianceRepository,
    ClusterHealthRepository,
    ClusterInventoryRepository,
    ClusterPolicyRepository,
    ClusterUpgradeRepository,
)
from app.repositories.reporting import (
    ClusterAuditRepository,
    ClusterEventRepository,
    ClusterReportRepository,
    ClusterStatisticRepository,
    ClusterWorkloadRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    clusters: ClusterRepository
    groups: ClusterGroupRepository
    regions: ClusterRegionRepository
    credentials: ClusterCredentialRepository
    versions: ClusterVersionRepository

    inventory: ClusterInventoryRepository
    health: ClusterHealthRepository
    capacity: ClusterCapacityRepository
    upgrades: ClusterUpgradeRepository
    compliance: ClusterComplianceRepository
    policies: ClusterPolicyRepository

    workloads: ClusterWorkloadRepository
    events: ClusterEventRepository
    statistics: ClusterStatisticRepository
    reports: ClusterReportRepository
    audit: ClusterAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        clusters=ClusterRepository(session, tenant_scope=tenant_scope),
        groups=ClusterGroupRepository(session, tenant_scope=tenant_scope),
        regions=ClusterRegionRepository(session, tenant_scope=tenant_scope),
        credentials=ClusterCredentialRepository(session, tenant_scope=tenant_scope),
        versions=ClusterVersionRepository(session, tenant_scope=tenant_scope),
        inventory=ClusterInventoryRepository(session, tenant_scope=tenant_scope),
        health=ClusterHealthRepository(session, tenant_scope=tenant_scope),
        capacity=ClusterCapacityRepository(session, tenant_scope=tenant_scope),
        upgrades=ClusterUpgradeRepository(session, tenant_scope=tenant_scope),
        compliance=ClusterComplianceRepository(session, tenant_scope=tenant_scope),
        policies=ClusterPolicyRepository(session, tenant_scope=tenant_scope),
        workloads=ClusterWorkloadRepository(session, tenant_scope=tenant_scope),
        events=ClusterEventRepository(session, tenant_scope=tenant_scope),
        statistics=ClusterStatisticRepository(session, tenant_scope=tenant_scope),
        reports=ClusterReportRepository(session, tenant_scope=tenant_scope),
        audit=ClusterAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
