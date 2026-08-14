"""Repositories for the fleet-wide reporting tables: rollup statistics,
generated reports, and the append-only audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportKind, ReportStatus
from app.models.reporting import EdgeAudit, EdgeReport, EdgeStatistic

MAX_PAGE_SIZE = 500


class EdgeStatisticRepository(BaseRepository[EdgeStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> EdgeStatistic | None:
        stmt = self._base_select().where(
            EdgeStatistic.organization_id == organization_id,
            EdgeStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[EdgeStatistic]:
        stmt = (
            self._base_select()
            .where(
                EdgeStatistic.organization_id == organization_id,
                EdgeStatistic.window_start >= since,
            )
            .order_by(EdgeStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeStatistic.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeReportRepository(BaseRepository[EdgeReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[EdgeReport]:
        stmt = self._base_select().where(EdgeReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(EdgeReport.kind == kind)
        if status is not None:
            stmt = stmt.where(EdgeReport.status == status)
        stmt = stmt.order_by(EdgeReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class EdgeAuditRepository(BaseRepository[EdgeAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[EdgeAudit]:
        stmt = self._base_select().where(EdgeAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(EdgeAudit.occurred_at >= since)
        stmt = stmt.order_by(EdgeAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[EdgeAudit]:
        stmt = (
            self._base_select()
            .where(EdgeAudit.entity_type == entity_type, EdgeAudit.entity_id == entity_id)
            .order_by(EdgeAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "EdgeAuditRepository",
    "EdgeReportRepository",
    "EdgeStatisticRepository",
]
