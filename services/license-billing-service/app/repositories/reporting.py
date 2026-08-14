"""Repositories for the fleet-wide reporting tables: rollup statistics,
generated reports, and the append-only audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportKind, ReportStatus
from app.models.reporting import BillingAudit, BillingReport, BillingStatistic

MAX_PAGE_SIZE = 500


class BillingStatisticRepository(BaseRepository[BillingStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BillingStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> BillingStatistic | None:
        stmt = self._base_select().where(
            BillingStatistic.organization_id == organization_id,
            BillingStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[BillingStatistic]:
        stmt = (
            self._base_select()
            .where(
                BillingStatistic.organization_id == organization_id,
                BillingStatistic.window_start >= since,
            )
            .order_by(BillingStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class BillingReportRepository(BaseRepository[BillingReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BillingReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[BillingReport]:
        stmt = self._base_select().where(BillingReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(BillingReport.kind == kind)
        if status is not None:
            stmt = stmt.where(BillingReport.status == status)
        stmt = stmt.order_by(BillingReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class BillingAuditRepository(BaseRepository[BillingAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BillingAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[BillingAudit]:
        stmt = self._base_select().where(BillingAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(BillingAudit.occurred_at >= since)
        stmt = stmt.order_by(BillingAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[BillingAudit]:
        stmt = (
            self._base_select()
            .where(BillingAudit.entity_type == entity_type, BillingAudit.entity_id == entity_id)
            .order_by(BillingAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "BillingAuditRepository",
    "BillingReportRepository",
    "BillingStatisticRepository",
]
