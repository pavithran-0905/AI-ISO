"""Repository for security findings."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FindingStatus
from app.models.security_findings import SecurityFinding

MAX_PAGE_SIZE = 500


class SecurityFindingRepository(BaseRepository[SecurityFinding]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SecurityFinding, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SecurityFinding]:
        stmt = (
            self._base_select()
            .where(SecurityFinding.organization_id == organization_id)
            .order_by(SecurityFinding.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: FindingStatus, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SecurityFinding]:
        stmt = (
            self._base_select()
            .where(
                SecurityFinding.organization_id == organization_id, SecurityFinding.status == status
            )
            .order_by(SecurityFinding.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SecurityFinding.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "SecurityFindingRepository"]
