"""Repositories for the provider/account/region/project tables."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import CloudAccount, CloudProject, CloudProvider, CloudRegion
from app.models.enums import CloudProviderType

MAX_PAGE_SIZE = 500


class CloudProviderRepository(BaseRepository[CloudProvider]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudProvider, tenant_scope=tenant_scope)

    async def find_by_type(
        self, organization_id: UUID, *, provider_type: CloudProviderType
    ) -> CloudProvider | None:
        stmt = self._base_select().where(
            CloudProvider.organization_id == organization_id,
            CloudProvider.provider_type == provider_type,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(self, organization_id: UUID) -> Sequence[CloudProvider]:
        stmt = self._base_select().where(
            CloudProvider.organization_id == organization_id, CloudProvider.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[CloudProvider]:
        stmt = (
            self._base_select()
            .where(CloudProvider.organization_id == organization_id)
            .order_by(CloudProvider.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class CloudAccountRepository(BaseRepository[CloudAccount]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudAccount, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, account_id: UUID) -> CloudAccount:
        stmt = self._base_select().where(
            CloudAccount.id == account_id, CloudAccount.organization_id == organization_id
        )
        found: CloudAccount | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Cloud account {account_id!s} was not found in this organization.")
        return found

    async def list_for_provider(self, provider_id: UUID) -> Sequence[CloudAccount]:
        stmt = self._base_select().where(CloudAccount.provider_id == provider_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[CloudAccount]:
        stmt = (
            self._base_select()
            .where(CloudAccount.organization_id == organization_id)
            .order_by(CloudAccount.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CloudAccount.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CloudRegionRepository(BaseRepository[CloudRegion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudRegion, tenant_scope=tenant_scope)

    async def list_for_provider(self, provider_id: UUID) -> Sequence[CloudRegion]:
        stmt = self._base_select().where(CloudRegion.provider_id == provider_id)
        return (await self._session.execute(stmt)).scalars().all()


class CloudProjectRepository(BaseRepository[CloudProject]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudProject, tenant_scope=tenant_scope)

    async def list_for_account(self, account_id: UUID) -> Sequence[CloudProject]:
        stmt = self._base_select().where(CloudProject.account_id == account_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "CloudAccountRepository",
    "CloudProjectRepository",
    "CloudProviderRepository",
    "CloudRegionRepository",
]
