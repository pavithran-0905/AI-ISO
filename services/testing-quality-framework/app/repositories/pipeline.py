"""Repository for pipeline results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TestRunStatus
from app.models.pipeline import PipelineResult

MAX_PAGE_SIZE = 500


class PipelineResultRepository(BaseRepository[PipelineResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PipelineResult, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[PipelineResult]:
        stmt = (
            self._base_select()
            .where(PipelineResult.organization_id == organization_id)
            .order_by(PipelineResult.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[PipelineResult]:
        stmt = (
            self._base_select()
            .where(
                PipelineResult.organization_id == organization_id,
                PipelineResult.status == TestRunStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(PipelineResult.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "PipelineResultRepository"]
