"""Repositories for sandbox sessions and mock service definitions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SandboxStatus
from app.models.sandbox import ApiMockService, ApiSandboxSession

MAX_PAGE_SIZE = 500


class ApiSandboxSessionRepository(BaseRepository[ApiSandboxSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiSandboxSession, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ApiSandboxSession]:
        stmt = (
            self._base_select()
            .where(
                ApiSandboxSession.organization_id == organization_id,
                ApiSandboxSession.status == SandboxStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_active_for_product(
        self, organization_id: UUID, *, developer_account_id: UUID, api_product_id: UUID
    ) -> ApiSandboxSession | None:
        stmt = self._base_select().where(
            ApiSandboxSession.organization_id == organization_id,
            ApiSandboxSession.developer_account_id == developer_account_id,
            ApiSandboxSession.api_product_id == api_product_id,
            ApiSandboxSession.status == SandboxStatus.ACTIVE,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ApiSandboxSession.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class ApiMockServiceRepository(BaseRepository[ApiMockService]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiMockService, tenant_scope=tenant_scope)

    async def list_for_product(self, api_product_id: UUID) -> Sequence[ApiMockService]:
        stmt = self._base_select().where(ApiMockService.api_product_id == api_product_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_for_endpoint(
        self, organization_id: UUID, *, api_product_id: UUID, endpoint_path: str
    ) -> ApiMockService | None:
        stmt = self._base_select().where(
            ApiMockService.organization_id == organization_id,
            ApiMockService.api_product_id == api_product_id,
            ApiMockService.endpoint_path == endpoint_path,
        )
        return (await self._session.execute(stmt)).scalars().first()


__all__ = ["MAX_PAGE_SIZE", "ApiMockServiceRepository", "ApiSandboxSessionRepository"]
