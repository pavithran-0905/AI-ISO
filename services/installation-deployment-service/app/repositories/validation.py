"""Repositories for pre-flight and dependency compatibility checks."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation import DependencyCheck, PreflightResult

MAX_PAGE_SIZE = 500


class PreflightResultRepository(BaseRepository[PreflightResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PreflightResult, tenant_scope=tenant_scope)

    async def list_for_session(self, installation_session_id: UUID) -> Sequence[PreflightResult]:
        stmt = self._base_select().where(
            PreflightResult.installation_session_id == installation_session_id
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[PreflightResult]:
        stmt = (
            self._base_select()
            .where(PreflightResult.organization_id == organization_id)
            .order_by(PreflightResult.checked_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DependencyCheckRepository(BaseRepository[DependencyCheck]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DependencyCheck, tenant_scope=tenant_scope)

    async def list_for_session(self, installation_session_id: UUID) -> Sequence[DependencyCheck]:
        stmt = self._base_select().where(
            DependencyCheck.installation_session_id == installation_session_id
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "DependencyCheckRepository", "PreflightResultRepository"]
