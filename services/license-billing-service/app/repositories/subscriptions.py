"""Repositories for subscription plans, features, and subscriptions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SubscriptionStatus
from app.models.subscriptions import Subscription, SubscriptionFeature, SubscriptionPlan

MAX_PAGE_SIZE = 500


class SubscriptionPlanRepository(BaseRepository[SubscriptionPlan]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SubscriptionPlan, tenant_scope=tenant_scope)

    async def list_enabled(self, organization_id: UUID) -> Sequence[SubscriptionPlan]:
        stmt = self._base_select().where(
            SubscriptionPlan.organization_id == organization_id,
            SubscriptionPlan.is_enabled.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().all()


class SubscriptionFeatureRepository(BaseRepository[SubscriptionFeature]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SubscriptionFeature, tenant_scope=tenant_scope)

    async def list_for_plan(self, plan_id: UUID) -> Sequence[SubscriptionFeature]:
        stmt = self._base_select().where(SubscriptionFeature.plan_id == plan_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_key(self, plan_id: UUID, *, feature_key: str) -> SubscriptionFeature | None:
        stmt = self._base_select().where(
            SubscriptionFeature.plan_id == plan_id, SubscriptionFeature.feature_key == feature_key
        )
        return (await self._session.execute(stmt)).scalars().first()


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Subscription, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, subscription_id: UUID) -> Subscription:
        stmt = self._base_select().where(
            Subscription.id == subscription_id, Subscription.organization_id == organization_id
        )
        found: Subscription | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Subscription {subscription_id!s} was not found in this organization."
            )
        return found

    async def list_for_customer(self, customer_id: UUID) -> Sequence[Subscription]:
        stmt = self._base_select().where(Subscription.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, status: SubscriptionStatus | None = None, limit: int = 100
    ) -> Sequence[Subscription]:
        stmt = self._base_select().where(Subscription.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Subscription.status == status)
        stmt = stmt.order_by(Subscription.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: SubscriptionStatus
    ) -> Sequence[Subscription]:
        stmt = self._base_select().where(
            Subscription.organization_id == organization_id, Subscription.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Subscription.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "SubscriptionFeatureRepository",
    "SubscriptionPlanRepository",
    "SubscriptionRepository",
]
