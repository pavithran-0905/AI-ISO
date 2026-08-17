"""API product governance, plans, and developer subscriptions.

Publishes ``SubscriptionActivated`` on every new subscription. Product
creation/approval has no dedicated event in docs/073's own EVENTS list
-- API publication is audited (``DeveloperAuditAction.API_PUBLICATION``)
but not separately broadcast, matching the spec's own scope exactly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import SubscriptionActivatedEvent
from app.models.enums import ApiProductStatus, ApiProductType, DeveloperAuditAction
from app.models.products import ApiPlan, ApiProduct, ApiSubscription
from app.products.engine import TransitionResult, validate_transition
from app.repositories.products import (
    ApiPlanRepository,
    ApiProductRepository,
    ApiSubscriptionRepository,
)
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "public-api-platform"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class ApiProductService:
    def __init__(self, repo: ApiProductRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        description: str,
        product_type: ApiProductType,
        now: datetime,
        actor_id: str | None = None,
    ) -> ApiProduct:
        product = await self._repo.create(
            ApiProduct(
                organization_id=organization_id,
                name=name,
                description=description,
                product_type=product_type,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=organization_id,
                action=DeveloperAuditAction.API_PUBLICATION,
                entity_type="api_product",
                entity_id=product.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"API product {name!r} created ({product_type.value}).",
            )
        return product

    async def transition(
        self,
        product: ApiProduct,
        *,
        target: ApiProductStatus,
        now: datetime,
        actor_id: str | None = None,
    ) -> ApiProduct:
        """Move *product* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(product.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        product.status = target
        if target == ApiProductStatus.APPROVED:
            product.approved_at = now
        await self._repo.update(product)

        if self._audit is not None:
            await self._audit.record(
                organization_id=product.organization_id,
                action=DeveloperAuditAction.API_PUBLICATION,
                entity_type="api_product",
                entity_id=product.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"API product {product.name!r} moved to {target.value}.",
            )
        return product


class ApiPlanService:
    def __init__(self, repo: ApiPlanRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        api_product_id: UUID,
        name: str,
        rate_limit_per_minute: int,
        quota_per_month: int,
    ) -> ApiPlan:
        return await self._repo.create(
            ApiPlan(
                organization_id=organization_id,
                api_product_id=api_product_id,
                name=name,
                rate_limit_per_minute=rate_limit_per_minute,
                quota_per_month=quota_per_month,
            )
        )


class ApiSubscriptionService:
    def __init__(
        self, repo: ApiSubscriptionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def subscribe(
        self, organization_id: UUID, *, developer_account_id: UUID, api_plan_id: UUID, now: datetime
    ) -> ApiSubscription:
        subscription = await self._repo.create(
            ApiSubscription(
                organization_id=organization_id,
                developer_account_id=developer_account_id,
                api_plan_id=api_plan_id,
                activated_at=now,
            )
        )
        await self._publish(
            SubscriptionActivatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "subscription_id": str(subscription.id),
                    "developer_account_id": str(developer_account_id),
                    "api_plan_id": str(api_plan_id),
                },
            )
        )
        return subscription


__all__ = [
    "ApiPlanService",
    "ApiProductService",
    "ApiSubscriptionService",
    "TransitionRefusedError",
]
