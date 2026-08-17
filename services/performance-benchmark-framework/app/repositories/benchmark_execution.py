"""Repositories for benchmark runs and their per-metric results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark_execution import BenchmarkResult, BenchmarkRun
from app.models.enums import BenchmarkRunStatus

MAX_PAGE_SIZE = 500


class BenchmarkRunRepository(BaseRepository[BenchmarkRun]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkRun, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, status: BenchmarkRunStatus | None = None, limit: int = 100
    ) -> Sequence[BenchmarkRun]:
        stmt = self._base_select().where(BenchmarkRun.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(BenchmarkRun.status == status)
        stmt = stmt.order_by(BenchmarkRun.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[BenchmarkRun]:
        stmt = (
            self._base_select()
            .where(
                BenchmarkRun.organization_id == organization_id,
                BenchmarkRun.status == BenchmarkRunStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(BenchmarkRun.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class BenchmarkResultRepository(BaseRepository[BenchmarkResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkResult, tenant_scope=tenant_scope)

    async def list_for_run(self, benchmark_run_id: UUID) -> Sequence[BenchmarkResult]:
        stmt = self._base_select().where(BenchmarkResult.benchmark_run_id == benchmark_run_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[BenchmarkResult]:
        stmt = (
            self._base_select()
            .where(BenchmarkResult.organization_id == organization_id)
            .order_by(BenchmarkResult.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(BenchmarkResult.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()

    async def list_distinct_suite_metric_pairs(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[tuple[UUID, str]]:
        stmt = (
            select(BenchmarkRun.benchmark_suite_id, BenchmarkResult.metric_name)
            .join(BenchmarkRun, BenchmarkResult.benchmark_run_id == BenchmarkRun.id)
            .where(BenchmarkResult.organization_id == organization_id)
            .distinct()
            .limit(limit)
        )
        return [(row[0], row[1]) for row in (await self._session.execute(stmt)).all()]

    async def list_latest_by_suite_metric(
        self, organization_id: UUID, *, benchmark_suite_id: UUID, metric_name: str, limit: int = 1
    ) -> Sequence[BenchmarkResult]:
        stmt = (
            select(BenchmarkResult)
            .join(BenchmarkRun, BenchmarkResult.benchmark_run_id == BenchmarkRun.id)
            .where(
                BenchmarkResult.organization_id == organization_id,
                BenchmarkRun.benchmark_suite_id == benchmark_suite_id,
                BenchmarkResult.metric_name == metric_name,
            )
            .order_by(BenchmarkResult.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "BenchmarkResultRepository", "BenchmarkRunRepository"]
