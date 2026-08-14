"""Repositories for the core fleet tables: clusters, groups, regions,
credentials, and the version catalog."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ClusterLifecycleState, ClusterType
from app.models.fleet import Cluster, ClusterCredential, ClusterGroup, ClusterRegion, ClusterVersion

MAX_PAGE_SIZE = 500


class ClusterRepository(BaseRepository[Cluster]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Cluster, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, name: str) -> Cluster | None:
        stmt = self._base_select().where(
            Cluster.organization_id == organization_id, Cluster.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(self, organization_id: UUID, cluster_id: UUID) -> Cluster:
        stmt = self._base_select().where(
            Cluster.id == cluster_id, Cluster.organization_id == organization_id
        )
        found: Cluster | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Cluster {cluster_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        lifecycle_state: ClusterLifecycleState | None = None,
        group_id: UUID | None = None,
        limit: int = 100,
    ) -> Sequence[Cluster]:
        stmt = self._base_select().where(Cluster.organization_id == organization_id)
        if lifecycle_state is not None:
            stmt = stmt.where(Cluster.lifecycle_state == lifecycle_state)
        if group_id is not None:
            stmt = stmt.where(Cluster.group_id == group_id)
        stmt = stmt.order_by(Cluster.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_active(self, organization_id: UUID) -> Sequence[Cluster]:
        stmt = self._base_select().where(
            Cluster.organization_id == organization_id,
            Cluster.lifecycle_state == ClusterLifecycleState.ACTIVE,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Cluster.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class ClusterGroupRepository(BaseRepository[ClusterGroup]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterGroup, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, name: str) -> ClusterGroup | None:
        stmt = self._base_select().where(
            ClusterGroup.organization_id == organization_id, ClusterGroup.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(self, organization_id: UUID) -> Sequence[ClusterGroup]:
        stmt = self._base_select().where(ClusterGroup.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class ClusterRegionRepository(BaseRepository[ClusterRegion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterRegion, tenant_scope=tenant_scope)

    async def list_all(self, organization_id: UUID) -> Sequence[ClusterRegion]:
        stmt = self._base_select().where(ClusterRegion.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class ClusterCredentialRepository(BaseRepository[ClusterCredential]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterCredential, tenant_scope=tenant_scope)

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterCredential]:
        stmt = self._base_select().where(ClusterCredential.cluster_id == cluster_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def latest_for_cluster(self, cluster_id: UUID) -> ClusterCredential | None:
        stmt = (
            self._base_select()
            .where(ClusterCredential.cluster_id == cluster_id)
            .order_by(ClusterCredential.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


class ClusterVersionRepository(BaseRepository[ClusterVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterVersion, tenant_scope=tenant_scope)

    async def find_by_type_and_version(
        self, cluster_type: ClusterType, version_label: str
    ) -> ClusterVersion | None:
        stmt = self._base_select().where(
            ClusterVersion.cluster_type == cluster_type,
            ClusterVersion.version_label == version_label,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_type(self, cluster_type: ClusterType) -> Sequence[ClusterVersion]:
        stmt = (
            self._base_select()
            .where(ClusterVersion.cluster_type == cluster_type)
            .order_by(ClusterVersion.skew_rank)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ClusterCredentialRepository",
    "ClusterGroupRepository",
    "ClusterRegionRepository",
    "ClusterRepository",
    "ClusterVersionRepository",
]
