"""Repository for compliance validation results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ComplianceResult
from app.models.enums import ComplianceFramework

MAX_PAGE_SIZE = 500


class ComplianceResultRepository(BaseRepository[ComplianceResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ComplianceResult, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ComplianceResult]:
        stmt = (
            self._base_select()
            .where(ComplianceResult.organization_id == organization_id)
            .order_by(ComplianceResult.evaluated_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_framework(
        self, organization_id: UUID, *, framework: ComplianceFramework, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ComplianceResult]:
        stmt = (
            self._base_select()
            .where(
                ComplianceResult.organization_id == organization_id,
                ComplianceResult.framework == framework,
            )
            .order_by(ComplianceResult.evaluated_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ComplianceResult.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ComplianceResultRepository"]
