"""Benchmark runs and the per-metric results within them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import BenchmarkRunStatus


class BenchmarkRun(BaseModel):
    """``benchmark_runs`` -- one execution of a benchmark suite -- see
    ``app.benchmark.engine`` for the transition table this drives."""

    __tablename__ = "benchmark_runs"
    __table_args__ = (
        Index("ix_benchmark_run_suite", "benchmark_suite_id"),
        Index("ix_benchmark_run_status", "status"),
    )

    benchmark_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_suites.id", ondelete="CASCADE"), index=True
    )
    benchmark_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("benchmark_profiles.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[BenchmarkRunStatus] = mapped_column(
        String(16), default=BenchmarkRunStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")


class BenchmarkResult(BaseModel):
    """``benchmark_results`` -- one metric measurement collected during a
    benchmark run."""

    __tablename__ = "benchmark_results"
    __table_args__ = (Index("ix_benchmark_result_run", "benchmark_run_id"),)

    benchmark_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True
    )
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")


__all__ = ["BenchmarkResult", "BenchmarkRun"]
