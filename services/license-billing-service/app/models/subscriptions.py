"""Subscription plans, their feature entitlements, and customer
subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import BillingModel, SubscriptionStatus


class SubscriptionPlan(BaseModel):
    """``subscription_plans`` -- one catalog entry a customer can
    subscribe to."""

    __tablename__ = "subscription_plans"
    __table_args__ = (Index("ix_subscription_plan_billing_model", "billing_model"),)

    name: Mapped[str] = mapped_column(String(255), index=True)
    billing_model: Mapped[BillingModel] = mapped_column(String(24), index=True)
    base_price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SubscriptionFeature(BaseModel):
    """``subscription_features`` -- one feature entitlement a plan
    grants, with an optional numeric limit (``None`` means unlimited)."""

    __tablename__ = "subscription_features"
    __table_args__ = (Index("ix_subscription_feature_plan", "plan_id"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="CASCADE"), index=True
    )
    feature_key: Mapped[str] = mapped_column(String(128), index=True)
    limit_value: Mapped[int | None] = mapped_column(Integer, default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(BaseModel):
    """``subscriptions`` -- one customer's subscription to a plan."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscription_customer", "customer_id"),
        Index("ix_subscription_plan", "plan_id"),
        Index("ix_subscription_status", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(16), default=SubscriptionStatus.TRIAL, index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = ["Subscription", "SubscriptionFeature", "SubscriptionPlan"]
