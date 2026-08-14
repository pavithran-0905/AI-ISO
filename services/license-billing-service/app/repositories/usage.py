"""Repositories for usage records, counters, quotas, and quota usage."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import Quota, QuotaUsage, UsageCounter, UsageRecord

MAX_PAGE_SIZE = 500


class UsageRecordRepository(BaseRepository[UsageRecord]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UsageRecord, tenant_scope=tenant_scope)

    async def list_for_customer(
        self, customer_id: UUID, *, metric_key: str | None = None, since: datetime, limit: int = 500
    ) -> Sequence[UsageRecord]:
        stmt = self._base_select().where(
            UsageRecord.customer_id == customer_id, UsageRecord.recorded_at >= since
        )
        if metric_key is not None:
            stmt = stmt.where(UsageRecord.metric_key == metric_key)
        stmt = stmt.order_by(UsageRecord.recorded_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class UsageCounterRepository(BaseRepository[UsageCounter]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, UsageCounter, tenant_scope=tenant_scope)

    async def find_window(
        self, customer_id: UUID, *, metric_key: str, period_start: datetime
    ) -> UsageCounter | None:
        stmt = self._base_select().where(
            UsageCounter.customer_id == customer_id,
            UsageCounter.metric_key == metric_key,
            UsageCounter.period_start == period_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_customer(self, customer_id: UUID) -> Sequence[UsageCounter]:
        stmt = self._base_select().where(UsageCounter.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()


class QuotaRepository(BaseRepository[Quota]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Quota, tenant_scope=tenant_scope)

    async def list_for_customer(self, customer_id: UUID) -> Sequence[Quota]:
        stmt = self._base_select().where(Quota.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_metric(self, customer_id: UUID, *, metric_key: str) -> Quota | None:
        stmt = self._base_select().where(
            Quota.customer_id == customer_id, Quota.metric_key == metric_key
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[Quota]:
        stmt = (
            self._base_select()
            .where(Quota.organization_id == organization_id)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Quota.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class QuotaUsageRepository(BaseRepository[QuotaUsage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, QuotaUsage, tenant_scope=tenant_scope)

    async def find_window(self, quota_id: UUID, *, period_start: datetime) -> QuotaUsage | None:
        stmt = self._base_select().where(
            QuotaUsage.quota_id == quota_id, QuotaUsage.period_start == period_start
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_quota(self, quota_id: UUID) -> Sequence[QuotaUsage]:
        stmt = self._base_select().where(QuotaUsage.quota_id == quota_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "QuotaRepository",
    "QuotaUsageRepository",
    "UsageCounterRepository",
    "UsageRecordRepository",
]
