"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReleaseReportKind, ReportStatus
from app.models.reporting import ReleaseAudit, ReleaseReport, ReleaseStatistic

MAX_PAGE_SIZE = 500


class ReleaseStatisticRepository(BaseRepository[ReleaseStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> ReleaseStatistic | None:
        stmt = self._base_select().where(
            ReleaseStatistic.organization_id == organization_id,
            ReleaseStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[ReleaseStatistic]:
        stmt = (
            self._base_select()
            .where(
                ReleaseStatistic.organization_id == organization_id,
                ReleaseStatistic.window_start >= since,
            )
            .order_by(ReleaseStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ReleaseReportRepository(BaseRepository[ReleaseReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReleaseReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[ReleaseReport]:
        stmt = self._base_select().where(ReleaseReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(ReleaseReport.kind == kind)
        if status is not None:
            stmt = stmt.where(ReleaseReport.status == status)
        stmt = stmt.order_by(ReleaseReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class ReleaseAuditRepository(BaseRepository[ReleaseAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[ReleaseAudit]:
        stmt = self._base_select().where(ReleaseAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(ReleaseAudit.occurred_at >= since)
        stmt = stmt.order_by(ReleaseAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[ReleaseAudit]:
        stmt = (
            self._base_select()
            .where(ReleaseAudit.entity_type == entity_type, ReleaseAudit.entity_id == entity_id)
            .order_by(ReleaseAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ReleaseAuditRepository",
    "ReleaseReportRepository",
    "ReleaseStatisticRepository",
]
