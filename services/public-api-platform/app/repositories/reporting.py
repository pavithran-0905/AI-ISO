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
from app.models.reporting import DeveloperAudit, DeveloperReport, DeveloperStatistic

MAX_PAGE_SIZE = 500


class DeveloperStatisticRepository(BaseRepository[DeveloperStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> DeveloperStatistic | None:
        stmt = self._base_select().where(
            DeveloperStatistic.organization_id == organization_id,
            DeveloperStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[DeveloperStatistic]:
        stmt = (
            self._base_select()
            .where(
                DeveloperStatistic.organization_id == organization_id,
                DeveloperStatistic.window_start >= since,
            )
            .order_by(DeveloperStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DeveloperReportRepository(BaseRepository[DeveloperReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[DeveloperReport]:
        stmt = self._base_select().where(DeveloperReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(DeveloperReport.kind == kind)
        if status is not None:
            stmt = stmt.where(DeveloperReport.status == status)
        stmt = stmt.order_by(DeveloperReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class DeveloperAuditRepository(BaseRepository[DeveloperAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[DeveloperAudit]:
        stmt = self._base_select().where(DeveloperAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(DeveloperAudit.occurred_at >= since)
        stmt = stmt.order_by(DeveloperAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[DeveloperAudit]:
        stmt = (
            self._base_select()
            .where(DeveloperAudit.entity_type == entity_type, DeveloperAudit.entity_id == entity_id)
            .order_by(DeveloperAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "DeveloperAuditRepository",
    "DeveloperReportRepository",
    "DeveloperStatisticRepository",
]
