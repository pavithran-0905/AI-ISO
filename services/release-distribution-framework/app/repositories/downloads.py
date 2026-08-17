"""Repository for download statistics."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.downloads import DownloadStatistic

MAX_PAGE_SIZE = 500


class DownloadStatisticRepository(BaseRepository[DownloadStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DownloadStatistic, tenant_scope=tenant_scope)

    async def list_for_artifact(self, release_artifact_id: UUID) -> Sequence[DownloadStatistic]:
        stmt = self._base_select().where(
            DownloadStatistic.release_artifact_id == release_artifact_id
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DownloadStatistic]:
        stmt = (
            self._base_select()
            .where(DownloadStatistic.organization_id == organization_id)
            .order_by(DownloadStatistic.downloaded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DownloadStatistic.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "DownloadStatisticRepository"]
