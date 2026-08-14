"""Repositories for synchronization jobs and the offline action queue."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SyncQueueStatus
from app.models.sync import MobileSyncJob, MobileSyncQueueItem

MAX_PAGE_SIZE = 500


class MobileSyncJobRepository(BaseRepository[MobileSyncJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileSyncJob, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[MobileSyncJob]:
        stmt = (
            self._base_select()
            .where(MobileSyncJob.organization_id == organization_id)
            .order_by(MobileSyncJob.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_device(
        self, organization_id: UUID, *, device_id: UUID, limit: int = 100
    ) -> Sequence[MobileSyncJob]:
        stmt = (
            self._base_select()
            .where(
                MobileSyncJob.organization_id == organization_id,
                MobileSyncJob.device_id == device_id,
            )
            .order_by(MobileSyncJob.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class MobileSyncQueueItemRepository(BaseRepository[MobileSyncQueueItem]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileSyncQueueItem, tenant_scope=tenant_scope)

    async def list_for_job(self, sync_job_id: UUID) -> Sequence[MobileSyncQueueItem]:
        stmt = self._base_select().where(MobileSyncQueueItem.sync_job_id == sync_job_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_queued(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MobileSyncQueueItem]:
        stmt = (
            self._base_select()
            .where(
                MobileSyncQueueItem.organization_id == organization_id,
                MobileSyncQueueItem.status == SyncQueueStatus.QUEUED,
            )
            .order_by(MobileSyncQueueItem.created_at.asc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MobileSyncQueueItem.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "MobileSyncJobRepository", "MobileSyncQueueItemRepository"]
