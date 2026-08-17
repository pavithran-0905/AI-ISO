"""Repositories for performance profiles and their raw metric points."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance import PerformanceMetric, PerformanceProfile

MAX_PAGE_SIZE = 500


class PerformanceProfileRepository(BaseRepository[PerformanceProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PerformanceProfile, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[PerformanceProfile]:
        stmt = (
            self._base_select()
            .where(PerformanceProfile.organization_id == organization_id)
            .order_by(PerformanceProfile.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class PerformanceMetricRepository(BaseRepository[PerformanceMetric]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PerformanceMetric, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[PerformanceMetric]:
        stmt = (
            self._base_select()
            .where(PerformanceMetric.organization_id == organization_id)
            .order_by(PerformanceMetric.recorded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(PerformanceMetric.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "PerformanceMetricRepository", "PerformanceProfileRepository"]
