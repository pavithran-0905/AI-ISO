"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportStatus, UpgradeReportKind
from app.models.reporting import UpgradeAudit, UpgradeReport, UpgradeStatistic

MAX_PAGE_SIZE = 500


class UpgradeStatisticRepository(BaseRepository[UpgradeStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> UpgradeStatistic | None:
        stmt = self._base_select().where(
            UpgradeStatistic.organization_id == organization_id,
            UpgradeStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[UpgradeStatistic]:
        stmt = (
            self._base_select()
            .where(
                UpgradeStatistic.organization_id == organization_id,
                UpgradeStatistic.window_start >= since,
            )
            .order_by(UpgradeStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeReportRepository(BaseRepository[UpgradeReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: UpgradeReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[UpgradeReport]:
        stmt = self._base_select().where(UpgradeReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(UpgradeReport.kind == kind)
        if status is not None:
            stmt = stmt.where(UpgradeReport.status == status)
        stmt = stmt.order_by(UpgradeReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeAuditRepository(BaseRepository[UpgradeAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[UpgradeAudit]:
        stmt = self._base_select().where(UpgradeAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(UpgradeAudit.occurred_at >= since)
        stmt = stmt.order_by(UpgradeAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[UpgradeAudit]:
        stmt = (
            self._base_select()
            .where(UpgradeAudit.entity_type == entity_type, UpgradeAudit.entity_id == entity_id)
            .order_by(UpgradeAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "UpgradeAuditRepository",
    "UpgradeReportRepository",
    "UpgradeStatisticRepository",
]
