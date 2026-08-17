"""Repositories for raw usage events, rate limits, and quotas."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import QuotaType
from app.models.usage import ApiQuota, ApiRateLimit, ApiUsageEvent

MAX_PAGE_SIZE = 5_000


class ApiUsageEventRepository(BaseRepository[ApiUsageEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiUsageEvent, tenant_scope=tenant_scope)

    async def list_since(
        self, organization_id: UUID, *, since: datetime, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ApiUsageEvent]:
        stmt = (
            self._base_select()
            .where(
                ApiUsageEvent.organization_id == organization_id,
                ApiUsageEvent.occurred_at >= since,
            )
            .order_by(ApiUsageEvent.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_developer(
        self,
        organization_id: UUID,
        *,
        developer_account_id: UUID,
        since: datetime,
        limit: int = 500,
    ) -> Sequence[ApiUsageEvent]:
        stmt = (
            self._base_select()
            .where(
                ApiUsageEvent.organization_id == organization_id,
                ApiUsageEvent.developer_account_id == developer_account_id,
                ApiUsageEvent.occurred_at >= since,
            )
            .order_by(ApiUsageEvent.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ApiUsageEvent.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class ApiRateLimitRepository(BaseRepository[ApiRateLimit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiRateLimit, tenant_scope=tenant_scope)

    async def find_for_plan(self, api_plan_id: UUID) -> ApiRateLimit | None:
        stmt = self._base_select().where(ApiRateLimit.api_plan_id == api_plan_id)
        return (await self._session.execute(stmt)).scalars().first()


class ApiQuotaRepository(BaseRepository[ApiQuota]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiQuota, tenant_scope=tenant_scope)

    async def find(
        self, organization_id: UUID, *, developer_account_id: UUID, quota_type: QuotaType
    ) -> ApiQuota | None:
        stmt = self._base_select().where(
            ApiQuota.organization_id == organization_id,
            ApiQuota.developer_account_id == developer_account_id,
            ApiQuota.quota_type == quota_type,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_developer(
        self, organization_id: UUID, *, developer_account_id: UUID
    ) -> Sequence[ApiQuota]:
        stmt = self._base_select().where(
            ApiQuota.organization_id == organization_id,
            ApiQuota.developer_account_id == developer_account_id,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ApiQuota]:
        stmt = self._base_select().where(ApiQuota.organization_id == organization_id).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ApiQuota.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ApiQuotaRepository",
    "ApiRateLimitRepository",
    "ApiUsageEventRepository",
]
