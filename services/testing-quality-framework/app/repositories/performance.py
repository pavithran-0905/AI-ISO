"""Repositories for performance results and benchmark results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance import BenchmarkResult, PerformanceResult

MAX_PAGE_SIZE = 500


class PerformanceResultRepository(BaseRepository[PerformanceResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PerformanceResult, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[PerformanceResult]:
        stmt = (
            self._base_select()
            .where(PerformanceResult.organization_id == organization_id)
            .order_by(PerformanceResult.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class BenchmarkResultRepository(BaseRepository[BenchmarkResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkResult, tenant_scope=tenant_scope)

    async def find_latest_by_name(
        self, organization_id: UUID, *, name: str
    ) -> BenchmarkResult | None:
        stmt = (
            self._base_select()
            .where(BenchmarkResult.organization_id == organization_id, BenchmarkResult.name == name)
            .order_by(BenchmarkResult.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[BenchmarkResult]:
        stmt = (
            self._base_select()
            .where(BenchmarkResult.organization_id == organization_id)
            .order_by(BenchmarkResult.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "BenchmarkResultRepository", "PerformanceResultRepository"]
