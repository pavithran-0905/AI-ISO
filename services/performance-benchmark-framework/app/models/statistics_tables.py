"""Windowed latency and throughput statistics."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class LatencyStatistics(BaseModel):
    """``latency_statistics`` -- one target's own latency percentile
    summary for one window."""

    __tablename__ = "latency_statistics"
    __table_args__ = (Index("ix_latency_statistics_target", "target_name"),)

    target_name: Mapped[str] = mapped_column(String(256), index=True)
    p50_ms: Mapped[float] = mapped_column(Float)
    p95_ms: Mapped[float] = mapped_column(Float)
    p99_ms: Mapped[float] = mapped_column(Float)
    max_ms: Mapped[float] = mapped_column(Float)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ThroughputStatistics(BaseModel):
    """``throughput_statistics`` -- one target's own request-rate summary
    for one window."""

    __tablename__ = "throughput_statistics"
    __table_args__ = (Index("ix_throughput_statistics_target", "target_name"),)

    target_name: Mapped[str] = mapped_column(String(256), index=True)
    requests_per_second: Mapped[float] = mapped_column(Float)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["LatencyStatistics", "ThroughputStatistics"]
