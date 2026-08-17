"""Raw API usage events, rate limit configuration, and quota tracking."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import QuotaResetPolicy, QuotaType


class ApiUsageEvent(BaseModel):
    """``api_usage`` -- one raw recorded API call."""

    __tablename__ = "api_usage"
    __table_args__ = (
        Index("ix_api_usage_developer", "developer_account_id"),
        Index("ix_api_usage_application", "application_id"),
        Index("ix_api_usage_occurred_at", "occurred_at"),
    )

    developer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_applications.id", ondelete="CASCADE"), index=True
    )
    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(String(256))
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApiRateLimit(BaseModel):
    """``api_rate_limits`` -- one plan's configured rate limit
    thresholds."""

    __tablename__ = "api_rate_limits"
    __table_args__ = (Index("ix_api_rate_limit_plan", "api_plan_id"),)

    api_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_plans.id", ondelete="CASCADE"), unique=True, index=True
    )
    requests_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    requests_per_hour: Mapped[int] = mapped_column(Integer, default=1_000)
    requests_per_day: Mapped[int] = mapped_column(Integer, default=10_000)
    burst_limit: Mapped[int] = mapped_column(Integer, default=20)
    concurrent_limit: Mapped[int] = mapped_column(Integer, default=10)


class ApiQuota(BaseModel):
    """``api_quotas`` -- one developer account's consumption against
    one quota type for the current reset period."""

    __tablename__ = "api_quotas"
    __table_args__ = (
        Index("ix_api_quota_developer", "developer_account_id"),
        Index("ix_api_quota_type", "quota_type"),
    )

    developer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    quota_type: Mapped[QuotaType] = mapped_column(String(16), index=True)
    limit_value: Mapped[int] = mapped_column(Integer)
    used_value: Mapped[int] = mapped_column(Integer, default=0)
    reset_policy: Mapped[QuotaResetPolicy] = mapped_column(
        String(8), default=QuotaResetPolicy.MONTHLY
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["ApiQuota", "ApiRateLimit", "ApiUsageEvent"]
