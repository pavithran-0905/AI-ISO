"""Repositories for API products, plans, and subscriptions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ApiProductStatus, SubscriptionStatus
from app.models.products import ApiPlan, ApiProduct, ApiSubscription

MAX_PAGE_SIZE = 500


class ApiProductRepository(BaseRepository[ApiProduct]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiProduct, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        status: ApiProductStatus | None = None,
        limit: int = 100,
    ) -> Sequence[ApiProduct]:
        stmt = self._base_select().where(ApiProduct.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(ApiProduct.status == status)
        stmt = stmt.order_by(ApiProduct.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class ApiPlanRepository(BaseRepository[ApiPlan]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiPlan, tenant_scope=tenant_scope)

    async def list_for_product(self, api_product_id: UUID) -> Sequence[ApiPlan]:
        stmt = self._base_select().where(ApiPlan.api_product_id == api_product_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[ApiPlan]:
        stmt = (
            self._base_select()
            .where(ApiPlan.organization_id == organization_id)
            .order_by(ApiPlan.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ApiSubscriptionRepository(BaseRepository[ApiSubscription]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiSubscription, tenant_scope=tenant_scope)

    async def find_active(
        self, organization_id: UUID, *, developer_account_id: UUID, api_plan_id: UUID
    ) -> ApiSubscription | None:
        stmt = self._base_select().where(
            ApiSubscription.organization_id == organization_id,
            ApiSubscription.developer_account_id == developer_account_id,
            ApiSubscription.api_plan_id == api_plan_id,
            ApiSubscription.status == SubscriptionStatus.ACTIVE,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_developer(
        self, organization_id: UUID, *, developer_account_id: UUID
    ) -> Sequence[ApiSubscription]:
        stmt = self._base_select().where(
            ApiSubscription.organization_id == organization_id,
            ApiSubscription.developer_account_id == developer_account_id,
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ApiPlanRepository",
    "ApiProductRepository",
    "ApiSubscriptionRepository",
]
