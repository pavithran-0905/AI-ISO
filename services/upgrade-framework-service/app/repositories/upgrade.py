"""Repositories for upgrade plans, jobs, history, fleet targets/results,
and declared dependencies."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UpgradeJobStatus
from app.models.upgrade import (
    UpgradeDependency,
    UpgradeHistory,
    UpgradeJob,
    UpgradePlan,
    UpgradeResult,
    UpgradeTarget,
)

MAX_PAGE_SIZE = 500


class UpgradePlanRepository(BaseRepository[UpgradePlan]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradePlan, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> UpgradePlan | None:
        stmt = self._base_select().where(
            UpgradePlan.organization_id == organization_id, UpgradePlan.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[UpgradePlan]:
        stmt = (
            self._base_select()
            .where(UpgradePlan.organization_id == organization_id, UpgradePlan.is_enabled.is_(True))
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeJobRepository(BaseRepository[UpgradeJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeJob, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, status: UpgradeJobStatus | None = None, limit: int = 100
    ) -> Sequence[UpgradeJob]:
        stmt = self._base_select().where(UpgradeJob.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(UpgradeJob.status == status)
        stmt = stmt.order_by(UpgradeJob.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[UpgradeJob]:
        stmt = (
            self._base_select()
            .where(
                UpgradeJob.organization_id == organization_id,
                UpgradeJob.status == UpgradeJobStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(UpgradeJob.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeHistoryRepository(BaseRepository[UpgradeHistory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeHistory, tenant_scope=tenant_scope)

    async def list_for_job(self, upgrade_job_id: UUID) -> Sequence[UpgradeHistory]:
        stmt = (
            self._base_select()
            .where(UpgradeHistory.upgrade_job_id == upgrade_job_id)
            .order_by(UpgradeHistory.occurred_at.asc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[UpgradeHistory]:
        stmt = (
            self._base_select()
            .where(UpgradeHistory.organization_id == organization_id)
            .order_by(UpgradeHistory.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeTargetRepository(BaseRepository[UpgradeTarget]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeTarget, tenant_scope=tenant_scope)

    async def list_for_job(self, upgrade_job_id: UUID) -> Sequence[UpgradeTarget]:
        stmt = self._base_select().where(UpgradeTarget.upgrade_job_id == upgrade_job_id)
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeResultRepository(BaseRepository[UpgradeResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeResult, tenant_scope=tenant_scope)

    async def list_for_target(self, upgrade_target_id: UUID) -> Sequence[UpgradeResult]:
        stmt = self._base_select().where(UpgradeResult.upgrade_target_id == upgrade_target_id)
        return (await self._session.execute(stmt)).scalars().all()


class UpgradeDependencyRepository(BaseRepository[UpgradeDependency]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UpgradeDependency, tenant_scope=tenant_scope)

    async def list_for_plan(self, upgrade_plan_id: UUID) -> Sequence[UpgradeDependency]:
        stmt = self._base_select().where(UpgradeDependency.upgrade_plan_id == upgrade_plan_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "UpgradeDependencyRepository",
    "UpgradeHistoryRepository",
    "UpgradeJobRepository",
    "UpgradePlanRepository",
    "UpgradeResultRepository",
    "UpgradeTargetRepository",
]
