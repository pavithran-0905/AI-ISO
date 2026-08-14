"""Repositories for the per-cluster operational tables: inventory,
health, capacity, upgrades, compliance, and policy propagation."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    CapacityResourceKind,
    ComplianceFramework,
    PolicyPropagationStatus,
    UpgradeStatus,
)
from app.models.operations import (
    ClusterCapacity,
    ClusterCompliance,
    ClusterHealth,
    ClusterInventory,
    ClusterPolicy,
    ClusterUpgrade,
)

MAX_PAGE_SIZE = 500


class ClusterInventoryRepository(BaseRepository[ClusterInventory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterInventory, tenant_scope=tenant_scope)

    async def latest_for_cluster(
        self, cluster_id: UUID, *, resource_kind: str
    ) -> ClusterInventory | None:
        stmt = (
            self._base_select()
            .where(
                ClusterInventory.cluster_id == cluster_id,
                ClusterInventory.resource_kind == resource_kind,
            )
            .order_by(ClusterInventory.collected_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterInventory]:
        stmt = self._base_select().where(ClusterInventory.cluster_id == cluster_id)
        return (await self._session.execute(stmt)).scalars().all()


class ClusterHealthRepository(BaseRepository[ClusterHealth]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterHealth, tenant_scope=tenant_scope)

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterHealth]:
        stmt = self._base_select().where(ClusterHealth.cluster_id == cluster_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def latest_per_component(self, cluster_id: UUID) -> Sequence[ClusterHealth]:
        """The most recent reading per component for one cluster.

        Reads every row for the cluster ordered newest-first and keeps
        only the first occurrence of each component -- the row count per
        cluster is small enough that a window-function query would add
        complexity this doesn't need.
        """
        stmt = (
            self._base_select()
            .where(ClusterHealth.cluster_id == cluster_id)
            .order_by(ClusterHealth.checked_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        seen: set[str] = set()
        latest: list[ClusterHealth] = []
        for row in rows:
            if row.component not in seen:
                seen.add(row.component)
                latest.append(row)
        return latest


class ClusterCapacityRepository(BaseRepository[ClusterCapacity]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterCapacity, tenant_scope=tenant_scope)

    async def latest_for_resource(
        self, cluster_id: UUID, *, resource_kind: CapacityResourceKind
    ) -> ClusterCapacity | None:
        stmt = (
            self._base_select()
            .where(
                ClusterCapacity.cluster_id == cluster_id,
                ClusterCapacity.resource_kind == resource_kind,
            )
            .order_by(ClusterCapacity.measured_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, cluster_id: UUID, *, resource_kind: CapacityResourceKind, limit: int = 100
    ) -> Sequence[ClusterCapacity]:
        stmt = (
            self._base_select()
            .where(
                ClusterCapacity.cluster_id == cluster_id,
                ClusterCapacity.resource_kind == resource_kind,
            )
            .order_by(ClusterCapacity.measured_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ClusterUpgradeRepository(BaseRepository[ClusterUpgrade]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterUpgrade, tenant_scope=tenant_scope)

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterUpgrade]:
        stmt = (
            self._base_select()
            .where(ClusterUpgrade.cluster_id == cluster_id)
            .order_by(ClusterUpgrade.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_in_progress(self, organization_id: UUID) -> Sequence[ClusterUpgrade]:
        stmt = self._base_select().where(
            ClusterUpgrade.organization_id == organization_id,
            ClusterUpgrade.status.in_([UpgradeStatus.PLANNED, UpgradeStatus.IN_PROGRESS]),
        )
        return (await self._session.execute(stmt)).scalars().all()


class ClusterComplianceRepository(BaseRepository[ClusterCompliance]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterCompliance, tenant_scope=tenant_scope)

    async def latest_for_framework(
        self, cluster_id: UUID, *, framework: ComplianceFramework
    ) -> ClusterCompliance | None:
        stmt = (
            self._base_select()
            .where(
                ClusterCompliance.cluster_id == cluster_id,
                ClusterCompliance.framework == framework,
            )
            .order_by(ClusterCompliance.assessed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterCompliance]:
        stmt = self._base_select().where(ClusterCompliance.cluster_id == cluster_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ClusterCompliance.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class ClusterPolicyRepository(BaseRepository[ClusterPolicy]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterPolicy, tenant_scope=tenant_scope)

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterPolicy]:
        stmt = self._base_select().where(ClusterPolicy.cluster_id == cluster_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_group(self, group_id: UUID) -> Sequence[ClusterPolicy]:
        stmt = self._base_select().where(ClusterPolicy.group_id == group_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_pending(self, organization_id: UUID) -> Sequence[ClusterPolicy]:
        stmt = self._base_select().where(
            ClusterPolicy.organization_id == organization_id,
            ClusterPolicy.propagation_status == PolicyPropagationStatus.PENDING,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_applied(self, organization_id: UUID) -> Sequence[ClusterPolicy]:
        stmt = self._base_select().where(
            ClusterPolicy.organization_id == organization_id,
            ClusterPolicy.propagation_status == PolicyPropagationStatus.APPLIED,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ClusterPolicy.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ClusterCapacityRepository",
    "ClusterComplianceRepository",
    "ClusterHealthRepository",
    "ClusterInventoryRepository",
    "ClusterPolicyRepository",
    "ClusterUpgradeRepository",
]
