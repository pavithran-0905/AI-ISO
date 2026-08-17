"""Repository for benchmark baselines."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baselines import BenchmarkBaseline

MAX_PAGE_SIZE = 500


class BenchmarkBaselineRepository(BaseRepository[BenchmarkBaseline]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkBaseline, tenant_scope=tenant_scope)

    async def find_by_suite_metric(
        self, organization_id: UUID, *, benchmark_suite_id: UUID, metric_name: str
    ) -> BenchmarkBaseline | None:
        stmt = self._base_select().where(
            BenchmarkBaseline.organization_id == organization_id,
            BenchmarkBaseline.benchmark_suite_id == benchmark_suite_id,
            BenchmarkBaseline.metric_name == metric_name,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[BenchmarkBaseline]:
        stmt = (
            self._base_select()
            .where(BenchmarkBaseline.organization_id == organization_id)
            .order_by(BenchmarkBaseline.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "BenchmarkBaselineRepository"]
