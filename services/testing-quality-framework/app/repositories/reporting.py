"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import QaReportKind, ReportStatus
from app.models.reporting import QaAudit, QaReport, QaStatistic

MAX_PAGE_SIZE = 500


class QaStatisticRepository(BaseRepository[QaStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, QaStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> QaStatistic | None:
        stmt = self._base_select().where(
            QaStatistic.organization_id == organization_id, QaStatistic.window_start == window_start
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[QaStatistic]:
        stmt = (
            self._base_select()
            .where(
                QaStatistic.organization_id == organization_id, QaStatistic.window_start >= since
            )
            .order_by(QaStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class QaReportRepository(BaseRepository[QaReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, QaReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: QaReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[QaReport]:
        stmt = self._base_select().where(QaReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(QaReport.kind == kind)
        if status is not None:
            stmt = stmt.where(QaReport.status == status)
        stmt = stmt.order_by(QaReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class QaAuditRepository(BaseRepository[QaAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, QaAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[QaAudit]:
        stmt = self._base_select().where(QaAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(QaAudit.occurred_at >= since)
        stmt = stmt.order_by(QaAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[QaAudit]:
        stmt = (
            self._base_select()
            .where(QaAudit.entity_type == entity_type, QaAudit.entity_id == entity_id)
            .order_by(QaAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "QaAuditRepository", "QaReportRepository", "QaStatisticRepository"]
