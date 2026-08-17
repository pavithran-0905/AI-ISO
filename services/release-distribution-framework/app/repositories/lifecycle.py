"""Repositories for LTS lifecycle tracking and end-of-life scheduling."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lifecycle import EolSchedule, LtsVersion

MAX_PAGE_SIZE = 500


class LtsVersionRepository(BaseRepository[LtsVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LtsVersion, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[LtsVersion]:
        stmt = (
            self._base_select()
            .where(LtsVersion.organization_id == organization_id)
            .order_by(LtsVersion.support_ends_at.asc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[LtsVersion]:
        stmt = (
            self._base_select()
            .where(LtsVersion.organization_id == organization_id, LtsVersion.is_active.is_(True))
            .order_by(LtsVersion.support_ends_at.asc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(LtsVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EolScheduleRepository(BaseRepository[EolSchedule]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EolSchedule, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[EolSchedule]:
        stmt = (
            self._base_select()
            .where(EolSchedule.organization_id == organization_id)
            .order_by(EolSchedule.eol_date.asc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EolSchedule.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "EolScheduleRepository", "LtsVersionRepository"]
