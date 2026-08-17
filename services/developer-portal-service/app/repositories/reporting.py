"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportKind, ReportStatus
from app.models.reporting import PortalAudit, PortalReport, PortalStatistic

MAX_PAGE_SIZE = 500


class PortalStatisticRepository(BaseRepository[PortalStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PortalStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> PortalStatistic | None:
        stmt = self._base_select().where(
            PortalStatistic.organization_id == organization_id,
            PortalStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[PortalStatistic]:
        stmt = (
            self._base_select()
            .where(
                PortalStatistic.organization_id == organization_id,
                PortalStatistic.window_start >= since,
            )
            .order_by(PortalStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class PortalReportRepository(BaseRepository[PortalReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PortalReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[PortalReport]:
        stmt = self._base_select().where(PortalReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(PortalReport.kind == kind)
        if status is not None:
            stmt = stmt.where(PortalReport.status == status)
        stmt = stmt.order_by(PortalReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class PortalAuditRepository(BaseRepository[PortalAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PortalAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[PortalAudit]:
        stmt = self._base_select().where(PortalAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(PortalAudit.occurred_at >= since)
        stmt = stmt.order_by(PortalAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[PortalAudit]:
        stmt = (
            self._base_select()
            .where(PortalAudit.entity_type == entity_type, PortalAudit.entity_id == entity_id)
            .order_by(PortalAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "PortalAuditRepository",
    "PortalReportRepository",
    "PortalStatisticRepository",
]
