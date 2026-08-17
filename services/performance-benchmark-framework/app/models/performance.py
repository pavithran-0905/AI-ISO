"""Performance profiles (what is being watched) and the raw metric
points collected against them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import BenchmarkType


class PerformanceProfile(BaseModel):
    """``performance_profiles`` -- one named performance-monitoring
    target."""

    __tablename__ = "performance_profiles"
    __table_args__ = (Index("ix_performance_profile_target_type", "target_type"),)

    name: Mapped[str] = mapped_column(String(256), index=True)
    target_type: Mapped[BenchmarkType] = mapped_column(String(24), index=True)


class PerformanceMetric(BaseModel):
    """``performance_metrics`` -- one raw metric point collected for a
    performance profile."""

    __tablename__ = "performance_metrics"
    __table_args__ = (Index("ix_performance_metric_profile", "performance_profile_id"),)

    performance_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("performance_profiles.id", ondelete="CASCADE"), index=True
    )
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["PerformanceMetric", "PerformanceProfile"]
