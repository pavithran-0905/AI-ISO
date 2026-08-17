"""Repositories for release distributions and regions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.distribution import ReleaseDistribution, ReleaseRegion

MAX_PAGE_SIZE = 500


class ReleaseDistributionRepository(BaseRepository[ReleaseDistribution]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseDistribution, tenant_scope=tenant_scope)

    async def list_for_version(self, release_version_id: UUID) -> Sequence[ReleaseDistribution]:
        stmt = self._base_select().where(
            ReleaseDistribution.release_version_id == release_version_id
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseDistribution]:
        stmt = (
            self._base_select()
            .where(ReleaseDistribution.organization_id == organization_id)
            .order_by(ReleaseDistribution.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ReleaseRegionRepository(BaseRepository[ReleaseRegion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseRegion, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseRegion]:
        stmt = (
            self._base_select()
            .where(ReleaseRegion.organization_id == organization_id)
            .order_by(ReleaseRegion.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleaseDistributionRepository", "ReleaseRegionRepository"]
