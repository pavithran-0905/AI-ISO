"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HardeningReportKind, ReportStatus
from app.models.reporting import HardeningAudit, HardeningReport, HardeningStatistic

MAX_PAGE_SIZE = 500


class HardeningStatisticRepository(BaseRepository[HardeningStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HardeningStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> HardeningStatistic | None:
        stmt = self._base_select().where(
            HardeningStatistic.organization_id == organization_id,
            HardeningStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[HardeningStatistic]:
        stmt = (
            self._base_select()
            .where(
                HardeningStatistic.organization_id == organization_id,
                HardeningStatistic.window_start >= since,
            )
            .order_by(HardeningStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class HardeningReportRepository(BaseRepository[HardeningReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HardeningReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: HardeningReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[HardeningReport]:
        stmt = self._base_select().where(HardeningReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(HardeningReport.kind == kind)
        if status is not None:
            stmt = stmt.where(HardeningReport.status == status)
        stmt = stmt.order_by(HardeningReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class HardeningAuditRepository(BaseRepository[HardeningAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HardeningAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[HardeningAudit]:
        stmt = self._base_select().where(HardeningAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(HardeningAudit.occurred_at >= since)
        stmt = stmt.order_by(HardeningAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[HardeningAudit]:
        stmt = (
            self._base_select()
            .where(HardeningAudit.entity_type == entity_type, HardeningAudit.entity_id == entity_id)
            .order_by(HardeningAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "HardeningAuditRepository",
    "HardeningReportRepository",
    "HardeningStatisticRepository",
]
