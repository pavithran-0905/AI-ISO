"""Subscription plan catalog and subscription lifecycle.

Wires ``app.subscriptions.engine``'s pure transition table onto the
repository that persists a subscription's ``status``, publishing the
lifecycle-boundary events docs/069 names.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import (
    SubscriptionCreatedEvent,
    SubscriptionExpiredEvent,
    SubscriptionRenewedEvent,
)
from app.models.enums import AuditAction, BillingModel, SubscriptionStatus
from app.models.subscriptions import Subscription, SubscriptionPlan
from app.repositories.subscriptions import SubscriptionPlanRepository, SubscriptionRepository
from app.services.audit import AuditService
from app.subscriptions.engine import TransitionResult, validate_transition
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class SubscriptionPlanService:
    def __init__(self, repo: SubscriptionPlanRepository) -> None:
        self._repo = repo

    async def create_plan(
        self,
        organization_id: UUID,
        *,
        name: str,
        billing_model: BillingModel,
        base_price: float,
        currency: str = "USD",
    ) -> SubscriptionPlan:
        return await self._repo.create(
            SubscriptionPlan(
                organization_id=organization_id,
                name=name,
                billing_model=billing_model,
                base_price=base_price,
                currency=currency,
            )
        )


class SubscriptionService:
    def __init__(
        self,
        repo: SubscriptionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def create_subscription(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        plan_id: UUID,
        start_at: datetime,
        current_period_end: datetime,
        actor_id: str | None,
        now: datetime,
    ) -> Subscription:
        subscription = await self._repo.create(
            Subscription(
                organization_id=organization_id,
                customer_id=customer_id,
                plan_id=plan_id,
                status=SubscriptionStatus.TRIAL,
                start_at=start_at,
                current_period_start=start_at,
                current_period_end=current_period_end,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.SUBSCRIPTION_CHANGED,
                entity_type="subscription",
                entity_id=subscription.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Created subscription {subscription.id!s} for customer {customer_id!s}.",
            )
        await self._publish(
            SubscriptionCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "subscription_id": str(subscription.id),
                    "customer_id": str(customer_id),
                    "plan_id": str(plan_id),
                },
            )
        )
        return subscription

    async def transition(
        self,
        subscription: Subscription,
        *,
        target: SubscriptionStatus,
        actor_id: str | None,
        now: datetime,
    ) -> Subscription:
        """Move *subscription* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(subscription.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        subscription.status = target
        await self._repo.update(subscription)

        if self._audit is not None:
            await self._audit.record(
                subscription.organization_id,
                action=AuditAction.SUBSCRIPTION_CHANGED,
                entity_type="subscription",
                entity_id=subscription.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Subscription {subscription.id!s} moved to {target.value}.",
            )

        if target == SubscriptionStatus.EXPIRED:
            await self._publish(
                SubscriptionExpiredEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=subscription.organization_id,
                    payload={
                        "subscription_id": str(subscription.id),
                        "customer_id": str(subscription.customer_id),
                    },
                )
            )
        return subscription

    async def renew(
        self, subscription: Subscription, *, new_period_end: datetime, now: datetime
    ) -> Subscription:
        """Renew an active subscription for another period, publishing
        ``SubscriptionRenewed``."""
        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = new_period_end
        subscription.status = SubscriptionStatus.ACTIVE
        await self._repo.update(subscription)
        await self._publish(
            SubscriptionRenewedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=subscription.organization_id,
                payload={
                    "subscription_id": str(subscription.id),
                    "current_period_end": new_period_end.isoformat(),
                },
            )
        )
        return subscription


__all__ = ["SubscriptionPlanService", "SubscriptionService", "TransitionRefusedError"]
