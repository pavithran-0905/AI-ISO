"""Repositories for generated reports and the immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportKind, ReportStatus
from app.models.reporting import MobileAudit, MobileReport

MAX_PAGE_SIZE = 500


class MobileReportRepository(BaseRepository[MobileReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileReport, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 100,
    ) -> Sequence[MobileReport]:
        stmt = self._base_select().where(MobileReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(MobileReport.kind == kind)
        if status is not None:
            stmt = stmt.where(MobileReport.status == status)
        stmt = stmt.order_by(MobileReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class MobileAuditRepository(BaseRepository[MobileAudit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[MobileAudit]:
        stmt = self._base_select().where(MobileAudit.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(MobileAudit.occurred_at >= since)
        stmt = stmt.order_by(MobileAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> Sequence[MobileAudit]:
        stmt = (
            self._base_select()
            .where(MobileAudit.entity_type == entity_type, MobileAudit.entity_id == entity_id)
            .order_by(MobileAudit.occurred_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "MobileAuditRepository", "MobileReportRepository"]
