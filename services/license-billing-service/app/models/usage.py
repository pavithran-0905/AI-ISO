"""Usage metering and quota tracking.

**A ``UsageRecord`` is an immutable event; ``UsageCounter`` is its
idempotent per-window rollup** -- matching the same statistics-table
discipline every AI-IOS service uses, applied here at the per-customer,
per-metric level rather than fleet-wide.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import QuotaLimitKind, QuotaPeriod


class UsageRecord(BaseModel):
    """``usage_records`` -- one raw metered event."""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_record_customer", "customer_id"),
        Index("ix_usage_record_metric", "metric_key"),
        Index("ix_usage_record_recorded_at", "recorded_at"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), default=None
    )
    metric_key: Mapped[str] = mapped_column(String(128), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UsageCounter(BaseModel):
    """``usage_counters`` -- one idempotent per-window rollup of usage
    for one customer and metric."""

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "customer_id",
            "metric_key",
            "period_start",
            name="uq_usage_counter_window",
        ),
        Index("ix_usage_counter_customer", "customer_id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    metric_key: Mapped[str] = mapped_column(String(128), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total_quantity: Mapped[float] = mapped_column(Float, default=0.0)


class Quota(BaseModel):
    """``quotas`` -- one limit definition for one customer and metric."""

    __tablename__ = "quotas"
    __table_args__ = (
        Index("ix_quota_customer", "customer_id"),
        Index("ix_quota_metric", "metric_key"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    metric_key: Mapped[str] = mapped_column(String(128), index=True)
    limit_value: Mapped[float] = mapped_column(Float)
    limit_kind: Mapped[QuotaLimitKind] = mapped_column(String(8), default=QuotaLimitKind.SOFT)
    period: Mapped[QuotaPeriod] = mapped_column(String(16), default=QuotaPeriod.MONTHLY)
    burst_limit: Mapped[float | None] = mapped_column(Float, default=None)
    """An additional allowance above ``limit_value`` a hard quota may
    permit briefly -- ``None`` means no burst allowance."""


class QuotaUsage(BaseModel):
    """``quota_usage`` -- one idempotent per-window usage-against-quota
    rollup."""

    __tablename__ = "quota_usage"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "quota_id", "period_start", name="uq_quota_usage_window"
        ),
        Index("ix_quota_usage_quota", "quota_id"),
    )

    quota_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotas.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_value: Mapped[float] = mapped_column(Float, default=0.0)


__all__ = ["Quota", "QuotaUsage", "UsageCounter", "UsageRecord"]
