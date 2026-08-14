"""Repositories for background system jobs and their history."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus
from app.models.jobs import JobHistory, SystemJob

MAX_PAGE_SIZE = 500


class SystemJobRepository(BaseRepository[SystemJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SystemJob, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, job_id: UUID) -> SystemJob:
        stmt = self._base_select().where(
            SystemJob.id == job_id, SystemJob.organization_id == organization_id
        )
        found: SystemJob | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Job {job_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: JobStatus | None = None, limit: int = 100
    ) -> Sequence[SystemJob]:
        stmt = self._base_select().where(SystemJob.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(SystemJob.status == status)
        stmt = stmt.order_by(SystemJob.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: JobStatus
    ) -> Sequence[SystemJob]:
        stmt = self._base_select().where(
            SystemJob.organization_id == organization_id, SystemJob.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SystemJob.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class JobHistoryRepository(BaseRepository[JobHistory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, JobHistory, tenant_scope=tenant_scope)

    async def list_for_job(self, job_id: UUID) -> Sequence[JobHistory]:
        stmt = (
            self._base_select()
            .where(JobHistory.job_id == job_id)
            .order_by(JobHistory.occurred_at.asc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "JobHistoryRepository", "SystemJobRepository"]
