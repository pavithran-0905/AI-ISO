"""Repository for coverage reports."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage import CoverageReport
from app.models.enums import CoverageType

MAX_PAGE_SIZE = 500


class CoverageReportRepository(BaseRepository[CoverageReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CoverageReport, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[CoverageReport]:
        stmt = (
            self._base_select()
            .where(CoverageReport.organization_id == organization_id)
            .order_by(CoverageReport.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_latest_by_type(
        self, organization_id: UUID, *, coverage_type: CoverageType, limit: int = 2
    ) -> Sequence[CoverageReport]:
        stmt = (
            self._base_select()
            .where(
                CoverageReport.organization_id == organization_id,
                CoverageReport.coverage_type == coverage_type,
            )
            .order_by(CoverageReport.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_distinct_types(self, organization_id: UUID) -> Sequence[CoverageType]:
        stmt = (
            select(CoverageReport.coverage_type)
            .where(CoverageReport.organization_id == organization_id)
            .distinct()
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CoverageReport.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CoverageReportRepository"]
