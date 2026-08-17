"""Repositories for benchmark suites and profiles."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark_definitions import BenchmarkProfile, BenchmarkSuite

MAX_PAGE_SIZE = 500


class BenchmarkSuiteRepository(BaseRepository[BenchmarkSuite]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkSuite, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> BenchmarkSuite | None:
        stmt = self._base_select().where(
            BenchmarkSuite.organization_id == organization_id, BenchmarkSuite.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[BenchmarkSuite]:
        stmt = (
            self._base_select()
            .where(BenchmarkSuite.organization_id == organization_id)
            .order_by(BenchmarkSuite.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class BenchmarkProfileRepository(BaseRepository[BenchmarkProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkProfile, tenant_scope=tenant_scope)

    async def list_for_suite(self, benchmark_suite_id: UUID) -> Sequence[BenchmarkProfile]:
        stmt = self._base_select().where(BenchmarkProfile.benchmark_suite_id == benchmark_suite_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "BenchmarkProfileRepository", "BenchmarkSuiteRepository"]
