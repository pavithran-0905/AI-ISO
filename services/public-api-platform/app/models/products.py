"""API products, their subscription plans, and developer subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ApiProductStatus, ApiProductType, SubscriptionStatus


class ApiProduct(BaseModel):
    """``api_products`` -- one published (or draft) API product."""

    __tablename__ = "api_products"
    __table_args__ = (
        Index("ix_api_product_type", "product_type"),
        Index("ix_api_product_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(String(4096), default="")
    product_type: Mapped[ApiProductType] = mapped_column(String(16), index=True)
    status: Mapped[ApiProductStatus] = mapped_column(
        String(24), default=ApiProductStatus.DRAFT, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ApiPlan(BaseModel):
    """``api_plans`` -- one subscribable plan for an API product."""

    __tablename__ = "api_plans"
    __table_args__ = (Index("ix_api_plan_product", "api_product_id"),)

    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    quota_per_month: Mapped[int] = mapped_column(Integer, default=100_000)


class ApiSubscription(BaseModel):
    """``api_subscriptions`` -- one developer account's subscription to
    a plan."""

    __tablename__ = "api_subscriptions"
    __table_args__ = (
        Index("ix_api_subscription_developer", "developer_account_id"),
        Index("ix_api_subscription_status", "status"),
    )

    developer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    api_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_plans.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(16), default=SubscriptionStatus.ACTIVE, index=True
    )
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["ApiPlan", "ApiProduct", "ApiSubscription"]
