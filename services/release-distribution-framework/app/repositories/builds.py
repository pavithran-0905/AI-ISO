"""Repository for release builds."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.builds import ReleaseBuild
from app.models.enums import BuildStatus

MAX_PAGE_SIZE = 500


class ReleaseBuildRepository(BaseRepository[ReleaseBuild]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseBuild, tenant_scope=tenant_scope)

    async def list_for_version(self, release_version_id: UUID) -> Sequence[ReleaseBuild]:
        stmt = self._base_select().where(ReleaseBuild.release_version_id == release_version_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseBuild]:
        stmt = (
            self._base_select()
            .where(ReleaseBuild.organization_id == organization_id)
            .order_by(ReleaseBuild.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseBuild]:
        stmt = (
            self._base_select()
            .where(
                ReleaseBuild.organization_id == organization_id,
                ReleaseBuild.status == BuildStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ReleaseBuild.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleaseBuildRepository"]
