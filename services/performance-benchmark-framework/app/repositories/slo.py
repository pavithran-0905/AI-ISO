"""Repository for SLO/SLI compliance results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slo import SloResult

MAX_PAGE_SIZE = 500


class SloResultRepository(BaseRepository[SloResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SloResult, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SloResult]:
        stmt = (
            self._base_select()
            .where(SloResult.organization_id == organization_id)
            .order_by(SloResult.evaluated_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_latest_by_name(
        self, organization_id: UUID, *, slo_name: str, limit: int = 1
    ) -> Sequence[SloResult]:
        stmt = (
            self._base_select()
            .where(SloResult.organization_id == organization_id, SloResult.slo_name == slo_name)
            .order_by(SloResult.evaluated_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_distinct_names(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[str]:
        stmt = (
            select(SloResult.slo_name)
            .where(SloResult.organization_id == organization_id)
            .distinct()
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SloResult.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "SloResultRepository"]
