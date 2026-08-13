"""Repositories for the operational tables: rolled-up statistics,
generated reports, and the immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportStatus
from app.models.operations import BackupAudit, BackupReport, BackupStatistic

MAX_PAGE_SIZE = 500


class BackupStatisticRepository(BaseRepository[BackupStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime, window_end: datetime
    ) -> BackupStatistic | None:
        stmt = self._base_select().where(
            BackupStatistic.organization_id == organization_id,
            BackupStatistic.window_start == window_start,
            BackupStatistic.window_end == window_end,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, start: datetime, end: datetime
    ) -> Sequence[BackupStatistic]:
        stmt = (
            self._base_select()
            .where(
                BackupStatistic.organization_id == organization_id,
                BackupStatistic.window_start >= start,
                BackupStatistic.window_end <= end,
            )
            .order_by(BackupStatistic.window_start)
        )
        return (await self._session.execute(stmt)).scalars().all()


class BackupReportRepository(BaseRepository[BackupReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupReport, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, report_id: UUID) -> BackupReport:
        stmt = self._base_select().where(
            BackupReport.id == report_id, BackupReport.organization_id == organization_id
        )
        found: BackupReport | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Report {report_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: ReportStatus | None = None, limit: int = 50
    ) -> Sequence[BackupReport]:
        stmt = self._base_select().where(BackupReport.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(BackupReport.status == status)
        stmt = stmt.order_by(BackupReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class BackupAuditRepository(BaseRepository[BackupAudit]):
    """Append-only repository for :class:`BackupAudit`.

    Intentionally exposes no ``update`` beyond the base soft-delete
    machinery: an audit trail that can be edited by the same path that
    writes it is not a trail, and this is the one service on the
    platform whose own audit trail is itself a disaster-recovery asset.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime, limit: int = 200
    ) -> Sequence[BackupAudit]:
        stmt = (
            self._base_select()
            .where(BackupAudit.organization_id == organization_id, BackupAudit.occurred_at >= since)
            .order_by(BackupAudit.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "BackupAuditRepository",
    "BackupReportRepository",
    "BackupStatisticRepository",
]
