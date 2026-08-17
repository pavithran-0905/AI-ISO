"""Repositories for security results and chaos results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_chaos import ChaosResult, SecurityResult

MAX_PAGE_SIZE = 500


class SecurityResultRepository(BaseRepository[SecurityResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SecurityResult, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SecurityResult]:
        stmt = (
            self._base_select()
            .where(SecurityResult.organization_id == organization_id)
            .order_by(SecurityResult.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class ChaosResultRepository(BaseRepository[ChaosResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ChaosResult, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ChaosResult]:
        stmt = (
            self._base_select()
            .where(ChaosResult.organization_id == organization_id)
            .order_by(ChaosResult.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ChaosResultRepository", "SecurityResultRepository"]
