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
from app.models.reporting import CloudAudit, CloudReport, CloudStatistic

MAX_PAGE_SIZE = 500


class CloudStatisticRepository(BaseRepository[CloudStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> CloudStatistic | None:
        stmt = self._base_select().where(
            CloudStatistic.organization_id == organization_id,
            CloudStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[CloudStatistic]:
        stmt = (
            self._base_select()
            .where(
                CloudStatistic.organization_id == organization_id,
                CloudStatistic.window_start >= since,
            )
            .order_by(CloudStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class CloudReportRepository(BaseRepository[CloudReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[CloudReport]:
        stmt = self._base_select().where(CloudReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(CloudReport.kind == kind)
        if status is not None:
            stmt = stmt.where(CloudReport.status == status)
        stmt = stmt.order_by(CloudReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class CloudAuditRepository(BaseRepository[CloudAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[CloudAudit]:
        stmt = self._base_select().where(CloudAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(CloudAudit.occurred_at >= since)
        stmt = stmt.order_by(CloudAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[CloudAudit]:
        stmt = (
            self._base_select()
            .where(CloudAudit.entity_type == entity_type, CloudAudit.entity_id == entity_id)
            .order_by(CloudAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "CloudAuditRepository",
    "CloudReportRepository",
    "CloudStatisticRepository",
]
