"""Repositories for upgrade and rollback history."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upgrade_rollback import RollbackHistory, UpgradeHistory

MAX_PAGE_SIZE = 500


class UpgradeHistoryRepository(BaseRepository[UpgradeHistory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeHistory, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[UpgradeHistory]:
        stmt = (
            self._base_select()
            .where(UpgradeHistory.organization_id == organization_id)
            .order_by(UpgradeHistory.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_job(self, deployment_job_id: UUID) -> Sequence[UpgradeHistory]:
        stmt = self._base_select().where(UpgradeHistory.deployment_job_id == deployment_job_id)
        return (await self._session.execute(stmt)).scalars().all()


class RollbackHistoryRepository(BaseRepository[RollbackHistory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RollbackHistory, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[RollbackHistory]:
        stmt = (
            self._base_select()
            .where(RollbackHistory.organization_id == organization_id)
            .order_by(RollbackHistory.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_job(self, deployment_job_id: UUID) -> Sequence[RollbackHistory]:
        stmt = self._base_select().where(RollbackHistory.deployment_job_id == deployment_job_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "RollbackHistoryRepository", "UpgradeHistoryRepository"]
