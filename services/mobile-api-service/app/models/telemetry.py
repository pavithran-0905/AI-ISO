"""Raw mobile telemetry and analytics events, as reported by clients."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import AnalyticsMetricType, TelemetryMetricType


class MobileTelemetryEvent(BaseModel):
    """``mobile_telemetry`` -- one raw telemetry reading reported by a
    device (app start, API performance, crash, network quality, ...)."""

    __tablename__ = "mobile_telemetry"
    __table_args__ = (
        Index("ix_mobile_telemetry_device", "device_id"),
        Index("ix_mobile_telemetry_metric_type", "metric_type"),
        Index("ix_mobile_telemetry_recorded_at", "recorded_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    metric_type: Mapped[TelemetryMetricType] = mapped_column(String(24), index=True)
    value: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MobileAnalyticsEvent(BaseModel):
    """``mobile_analytics`` -- one raw analytics reading (DAU/MAU,
    session duration, feature usage, ...)."""

    __tablename__ = "mobile_analytics"
    __table_args__ = (
        Index("ix_mobile_analytics_device", "device_id"),
        Index("ix_mobile_analytics_metric_type", "metric_type"),
        Index("ix_mobile_analytics_recorded_at", "recorded_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    metric_type: Mapped[AnalyticsMetricType] = mapped_column(String(32), index=True)
    value: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["MobileAnalyticsEvent", "MobileTelemetryEvent"]
