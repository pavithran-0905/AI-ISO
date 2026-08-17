"""Repository for release versions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.releases import ReleaseVersion

MAX_PAGE_SIZE = 500


class ReleaseVersionRepository(BaseRepository[ReleaseVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseVersion, tenant_scope=tenant_scope)

    async def find_by_label(
        self, organization_id: UUID, *, version_label: str
    ) -> ReleaseVersion | None:
        stmt = self._base_select().where(
            ReleaseVersion.organization_id == organization_id,
            ReleaseVersion.version_label == version_label,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseVersion]:
        stmt = (
            self._base_select()
            .where(ReleaseVersion.organization_id == organization_id)
            .order_by(ReleaseVersion.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseVersion]:
        return await self.list_all(organization_id, limit=limit)

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ReleaseVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleaseVersionRepository"]
