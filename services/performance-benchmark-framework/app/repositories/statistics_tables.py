"""Repositories for windowed latency and throughput statistics."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statistics_tables import LatencyStatistics, ThroughputStatistics

MAX_PAGE_SIZE = 500


class LatencyStatisticsRepository(BaseRepository[LatencyStatistics]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LatencyStatistics, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[LatencyStatistics]:
        stmt = (
            self._base_select()
            .where(LatencyStatistics.organization_id == organization_id)
            .order_by(LatencyStatistics.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ThroughputStatisticsRepository(BaseRepository[ThroughputStatistics]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ThroughputStatistics, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ThroughputStatistics]:
        stmt = (
            self._base_select()
            .where(ThroughputStatistics.organization_id == organization_id)
            .order_by(ThroughputStatistics.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "LatencyStatisticsRepository", "ThroughputStatisticsRepository"]
