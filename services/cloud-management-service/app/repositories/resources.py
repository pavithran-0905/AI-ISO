"""Repositories for the resource tables: the base resource row and its
per-category detail rows."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CloudResourceLifecycleState, CloudResourceType
from app.models.resources import (
    CloudCompute,
    CloudDatabase,
    CloudKubernetes,
    CloudNetwork,
    CloudResource,
    CloudStorage,
)

MAX_PAGE_SIZE = 500


class CloudResourceRepository(BaseRepository[CloudResource]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudResource, tenant_scope=tenant_scope)

    async def find_by_external_id(
        self, account_id: UUID, *, external_id: str
    ) -> CloudResource | None:
        stmt = self._base_select().where(
            CloudResource.account_id == account_id, CloudResource.external_id == external_id
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(self, organization_id: UUID, resource_id: UUID) -> CloudResource:
        stmt = self._base_select().where(
            CloudResource.id == resource_id, CloudResource.organization_id == organization_id
        )
        found: CloudResource | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Cloud resource {resource_id!s} was not found in this organization."
            )
        return found

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        account_id: UUID | None = None,
        resource_type: CloudResourceType | None = None,
        lifecycle_state: CloudResourceLifecycleState | None = None,
        limit: int = 100,
    ) -> Sequence[CloudResource]:
        stmt = self._base_select().where(CloudResource.organization_id == organization_id)
        if account_id is not None:
            stmt = stmt.where(CloudResource.account_id == account_id)
        if resource_type is not None:
            stmt = stmt.where(CloudResource.resource_type == resource_type)
        if lifecycle_state is not None:
            stmt = stmt.where(CloudResource.lifecycle_state == lifecycle_state)
        stmt = stmt.order_by(CloudResource.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CloudResource.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CloudComputeRepository(BaseRepository[CloudCompute]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudCompute, tenant_scope=tenant_scope)

    async def find_for_resource(self, resource_id: UUID) -> CloudCompute | None:
        stmt = self._base_select().where(CloudCompute.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_org(self, organization_id: UUID) -> Sequence[CloudCompute]:
        stmt = self._base_select().where(CloudCompute.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class CloudStorageRepository(BaseRepository[CloudStorage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudStorage, tenant_scope=tenant_scope)

    async def find_for_resource(self, resource_id: UUID) -> CloudStorage | None:
        stmt = self._base_select().where(CloudStorage.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().first()


class CloudNetworkRepository(BaseRepository[CloudNetwork]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudNetwork, tenant_scope=tenant_scope)

    async def find_for_resource(self, resource_id: UUID) -> CloudNetwork | None:
        stmt = self._base_select().where(CloudNetwork.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().first()


class CloudDatabaseRepository(BaseRepository[CloudDatabase]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudDatabase, tenant_scope=tenant_scope)

    async def find_for_resource(self, resource_id: UUID) -> CloudDatabase | None:
        stmt = self._base_select().where(CloudDatabase.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().first()


class CloudKubernetesRepository(BaseRepository[CloudKubernetes]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudKubernetes, tenant_scope=tenant_scope)

    async def find_for_resource(self, resource_id: UUID) -> CloudKubernetes | None:
        stmt = self._base_select().where(CloudKubernetes.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().first()


__all__ = [
    "MAX_PAGE_SIZE",
    "CloudComputeRepository",
    "CloudDatabaseRepository",
    "CloudKubernetesRepository",
    "CloudNetworkRepository",
    "CloudResourceRepository",
    "CloudStorageRepository",
]
