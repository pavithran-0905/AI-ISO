"""Marketplace subscription purchases.

Publishes ``MarketplacePurchaseCompleted``.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import MarketplacePurchaseCompletedEvent
from app.models.billing import MarketplaceSubscription
from app.models.enums import MarketplaceSubscriptionStatus
from app.repositories.billing import MarketplaceSubscriptionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class MarketplaceSubscriptionService:
    def __init__(
        self, repo: MarketplaceSubscriptionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def purchase(
        self, organization_id: UUID, *, customer_id: UUID, marketplace_ref: str, plan_id: UUID
    ) -> MarketplaceSubscription:
        subscription = await self._repo.create(
            MarketplaceSubscription(
                organization_id=organization_id,
                customer_id=customer_id,
                marketplace_ref=marketplace_ref,
                plan_id=plan_id,
                status=MarketplaceSubscriptionStatus.ACTIVE,
            )
        )
        await self._publish(
            MarketplacePurchaseCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "marketplace_subscription_id": str(subscription.id),
                    "customer_id": str(customer_id),
                },
            )
        )
        return subscription

    async def cancel(self, subscription: MarketplaceSubscription) -> MarketplaceSubscription:
        subscription.status = MarketplaceSubscriptionStatus.CANCELLED
        return await self._repo.update(subscription)


__all__ = ["MarketplaceSubscriptionService"]
