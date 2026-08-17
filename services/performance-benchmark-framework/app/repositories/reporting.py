"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BenchmarkReportKind, ReportStatus
from app.models.reporting import BenchmarkAudit, BenchmarkReport, BenchmarkStatistic

MAX_PAGE_SIZE = 500


class BenchmarkStatisticRepository(BaseRepository[BenchmarkStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> BenchmarkStatistic | None:
        stmt = self._base_select().where(
            BenchmarkStatistic.organization_id == organization_id,
            BenchmarkStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[BenchmarkStatistic]:
        stmt = (
            self._base_select()
            .where(
                BenchmarkStatistic.organization_id == organization_id,
                BenchmarkStatistic.window_start >= since,
            )
            .order_by(BenchmarkStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class BenchmarkReportRepository(BaseRepository[BenchmarkReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: BenchmarkReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[BenchmarkReport]:
        stmt = self._base_select().where(BenchmarkReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(BenchmarkReport.kind == kind)
        if status is not None:
            stmt = stmt.where(BenchmarkReport.status == status)
        stmt = stmt.order_by(BenchmarkReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class BenchmarkAuditRepository(BaseRepository[BenchmarkAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BenchmarkAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[BenchmarkAudit]:
        stmt = self._base_select().where(BenchmarkAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(BenchmarkAudit.occurred_at >= since)
        stmt = stmt.order_by(BenchmarkAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[BenchmarkAudit]:
        stmt = (
            self._base_select()
            .where(BenchmarkAudit.entity_type == entity_type, BenchmarkAudit.entity_id == entity_id)
            .order_by(BenchmarkAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "BenchmarkAuditRepository",
    "BenchmarkReportRepository",
    "BenchmarkStatisticRepository",
]
