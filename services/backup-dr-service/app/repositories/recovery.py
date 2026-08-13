"""Repositories for the recovery-side tables: restore, replication, DR
plans, DR tests, failover events, and recovery reports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DrPlanStatus, DrTestStatus, RestoreJobStatus
from app.models.recovery import (
    DrPlan,
    DrTest,
    FailoverEvent,
    RecoveryReport,
    ReplicationJob,
    RestoreJob,
    RestorePoint,
)

MAX_PAGE_SIZE = 500


class RestorePointRepository(BaseRepository[RestorePoint]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RestorePoint, tenant_scope=tenant_scope)

    async def list_for_target(self, target_id: UUID) -> Sequence[RestorePoint]:
        stmt = self._base_select().where(RestorePoint.target_id == target_id)
        return (await self._session.execute(stmt)).scalars().all()


class RestoreJobRepository(BaseRepository[RestoreJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RestoreJob, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, job_id: UUID) -> RestoreJob:
        stmt = self._base_select().where(
            RestoreJob.id == job_id, RestoreJob.organization_id == organization_id
        )
        found: RestoreJob | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Restore job {job_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: RestoreJobStatus | None = None, limit: int = 100
    ) -> Sequence[RestoreJob]:
        stmt = self._base_select().where(RestoreJob.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(RestoreJob.status == status)
        stmt = stmt.order_by(RestoreJob.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class ReplicationJobRepository(BaseRepository[ReplicationJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReplicationJob, tenant_scope=tenant_scope)

    async def list_for_organization(self, organization_id: UUID) -> Sequence[ReplicationJob]:
        stmt = self._base_select().where(ReplicationJob.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ReplicationJob.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DrPlanRepository(BaseRepository[DrPlan]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DrPlan, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, plan_id: UUID) -> DrPlan:
        stmt = self._base_select().where(
            DrPlan.id == plan_id, DrPlan.organization_id == organization_id
        )
        found: DrPlan | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"DR plan {plan_id!s} was not found in this organization.")
        return found

    async def list_active(self, organization_id: UUID) -> Sequence[DrPlan]:
        stmt = self._base_select().where(
            DrPlan.organization_id == organization_id,
            DrPlan.is_active.is_(True),
            DrPlan.status == DrPlanStatus.ACTIVE,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DrPlan.organization_id).distinct().where(DrPlan.is_active.is_(True))
        return (await self._session.execute(stmt)).scalars().all()


class DrTestRepository(BaseRepository[DrTest]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DrTest, tenant_scope=tenant_scope)

    async def list_for_plan(self, dr_plan_id: UUID, *, limit: int = 50) -> Sequence[DrTest]:
        stmt = (
            self._base_select()
            .where(DrTest.dr_plan_id == dr_plan_id)
            .order_by(DrTest.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_due(self, organization_id: UUID, *, now: datetime) -> Sequence[DrTest]:
        stmt = self._base_select().where(
            DrTest.organization_id == organization_id,
            DrTest.status == DrTestStatus.SCHEDULED,
            DrTest.scheduled_at.is_not(None),
            DrTest.scheduled_at <= now,
        )
        return (await self._session.execute(stmt)).scalars().all()


class FailoverEventRepository(BaseRepository[FailoverEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, FailoverEvent, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[FailoverEvent]:
        stmt = (
            self._base_select()
            .where(FailoverEvent.organization_id == organization_id)
            .order_by(FailoverEvent.initiated_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class RecoveryReportRepository(BaseRepository[RecoveryReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RecoveryReport, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[RecoveryReport]:
        stmt = (
            self._base_select()
            .where(RecoveryReport.organization_id == organization_id)
            .order_by(RecoveryReport.generated_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "DrPlanRepository",
    "DrTestRepository",
    "FailoverEventRepository",
    "RecoveryReportRepository",
    "ReplicationJobRepository",
    "RestoreJobRepository",
    "RestorePointRepository",
]
