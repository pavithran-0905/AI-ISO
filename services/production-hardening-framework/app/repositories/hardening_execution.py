"""Repositories for hardening runs and their per-check results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HardeningRunStatus
from app.models.hardening_execution import HardeningResult, HardeningRun

MAX_PAGE_SIZE = 500


class HardeningRunRepository(BaseRepository[HardeningRun]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HardeningRun, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, status: HardeningRunStatus | None = None, limit: int = 100
    ) -> Sequence[HardeningRun]:
        stmt = self._base_select().where(HardeningRun.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(HardeningRun.status == status)
        stmt = stmt.order_by(HardeningRun.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[HardeningRun]:
        stmt = (
            self._base_select()
            .where(
                HardeningRun.organization_id == organization_id,
                HardeningRun.status == HardeningRunStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(HardeningRun.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class HardeningResultRepository(BaseRepository[HardeningResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HardeningResult, tenant_scope=tenant_scope)

    async def list_for_run(self, hardening_run_id: UUID) -> Sequence[HardeningResult]:
        stmt = self._base_select().where(HardeningResult.hardening_run_id == hardening_run_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[HardeningResult]:
        stmt = (
            self._base_select()
            .where(HardeningResult.organization_id == organization_id)
            .order_by(HardeningResult.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "HardeningResultRepository", "HardeningRunRepository"]
