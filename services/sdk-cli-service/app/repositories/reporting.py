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
from app.models.reporting import CliReport, CliStatistic, SdkAudit

MAX_PAGE_SIZE = 500


class CliStatisticRepository(BaseRepository[CliStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> CliStatistic | None:
        stmt = self._base_select().where(
            CliStatistic.organization_id == organization_id,
            CliStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[CliStatistic]:
        stmt = (
            self._base_select()
            .where(
                CliStatistic.organization_id == organization_id, CliStatistic.window_start >= since
            )
            .order_by(CliStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class CliReportRepository(BaseRepository[CliReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[CliReport]:
        stmt = self._base_select().where(CliReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(CliReport.kind == kind)
        if status is not None:
            stmt = stmt.where(CliReport.status == status)
        stmt = stmt.order_by(CliReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class SdkAuditRepository(BaseRepository[SdkAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[SdkAudit]:
        stmt = self._base_select().where(SdkAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(SdkAudit.occurred_at >= since)
        stmt = stmt.order_by(SdkAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[SdkAudit]:
        stmt = (
            self._base_select()
            .where(SdkAudit.entity_type == entity_type, SdkAudit.entity_id == entity_id)
            .order_by(SdkAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SdkAudit.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CliReportRepository", "CliStatisticRepository", "SdkAuditRepository"]
