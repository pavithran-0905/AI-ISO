"""Repositories for rollup statistics, generated reports, and the
immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DeploymentReportKind, ReportStatus
from app.models.reporting import DeploymentAudit, DeploymentReport, DeploymentStatistic

MAX_PAGE_SIZE = 500


class DeploymentStatisticRepository(BaseRepository[DeploymentStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime
    ) -> DeploymentStatistic | None:
        stmt = self._base_select().where(
            DeploymentStatistic.organization_id == organization_id,
            DeploymentStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[DeploymentStatistic]:
        stmt = (
            self._base_select()
            .where(
                DeploymentStatistic.organization_id == organization_id,
                DeploymentStatistic.window_start >= since,
            )
            .order_by(DeploymentStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentReportRepository(BaseRepository[DeploymentReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: DeploymentReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[DeploymentReport]:
        stmt = self._base_select().where(DeploymentReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(DeploymentReport.kind == kind)
        if status is not None:
            stmt = stmt.where(DeploymentReport.status == status)
        stmt = stmt.order_by(DeploymentReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentAuditRepository(BaseRepository[DeploymentAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[DeploymentAudit]:
        stmt = self._base_select().where(DeploymentAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(DeploymentAudit.occurred_at >= since)
        stmt = stmt.order_by(DeploymentAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[DeploymentAudit]:
        stmt = (
            self._base_select()
            .where(
                DeploymentAudit.entity_type == entity_type, DeploymentAudit.entity_id == entity_id
            )
            .order_by(DeploymentAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "DeploymentAuditRepository",
    "DeploymentReportRepository",
    "DeploymentStatisticRepository",
]
