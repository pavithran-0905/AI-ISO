"""Repositories for API keys and their per-window usage rollup."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_management import ApiKey, ApiUsage
from app.models.enums import ApiKeyStatus

MAX_PAGE_SIZE = 500


class ApiKeyRepository(BaseRepository[ApiKey]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiKey, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, key_id: UUID) -> ApiKey:
        stmt = self._base_select().where(
            ApiKey.id == key_id, ApiKey.organization_id == organization_id
        )
        found: ApiKey | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"API key {key_id!s} was not found in this organization.")
        return found

    async def find_by_hash(self, key_hash: str) -> ApiKey | None:
        stmt = self._base_select().where(ApiKey.key_hash == key_hash)
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, status: ApiKeyStatus | None = None, limit: int = 100
    ) -> Sequence[ApiKey]:
        stmt = self._base_select().where(ApiKey.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(ApiKey.status == status)
        stmt = stmt.order_by(ApiKey.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: ApiKeyStatus
    ) -> Sequence[ApiKey]:
        stmt = self._base_select().where(
            ApiKey.organization_id == organization_id, ApiKey.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ApiKey.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class ApiUsageRepository(BaseRepository[ApiUsage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiUsage, tenant_scope=tenant_scope)

    async def find_window(self, api_key_id: UUID, *, window_start: datetime) -> ApiUsage | None:
        stmt = self._base_select().where(
            ApiUsage.api_key_id == api_key_id, ApiUsage.window_start == window_start
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_key(self, api_key_id: UUID) -> Sequence[ApiUsage]:
        stmt = self._base_select().where(ApiUsage.api_key_id == api_key_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def total_requests_for_org(self, organization_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            ApiUsage.organization_id == organization_id, ApiUsage.window_start >= since
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return sum(row.request_count for row in rows)


__all__ = ["MAX_PAGE_SIZE", "ApiKeyRepository", "ApiUsageRepository"]
