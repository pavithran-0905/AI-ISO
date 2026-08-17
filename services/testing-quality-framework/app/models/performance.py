"""Performance test results and benchmark results."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import PerformanceTestType


class PerformanceResult(BaseModel):
    """``performance_results`` -- one performance test's own
    measurement, optionally tied to the test run that produced it."""

    __tablename__ = "performance_results"
    __table_args__ = (Index("ix_performance_result_run", "test_run_id"),)

    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), default=None, index=True
    )
    performance_type: Mapped[PerformanceTestType] = mapped_column(String(24), index=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    throughput_rps: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[str] = mapped_column(Text, default="")


class BenchmarkResult(BaseModel):
    """``benchmark_results`` -- one benchmark's own baseline vs.
    measured comparison."""

    __tablename__ = "benchmark_results"

    name: Mapped[str] = mapped_column(String(128), index=True)
    baseline_value: Mapped[float] = mapped_column(Float)
    measured_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["BenchmarkResult", "PerformanceResult"]
