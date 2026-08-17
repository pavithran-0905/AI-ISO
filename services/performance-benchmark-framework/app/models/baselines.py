"""Benchmark baselines -- the comparison point regression detection and
improvement detection are measured against."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class BenchmarkBaseline(BaseModel):
    """``benchmark_baselines`` -- one suite's own accepted value for one
    metric, automatically set from that metric's first-ever recorded
    result (see ``BenchmarkResultService``) or replaced explicitly."""

    __tablename__ = "benchmark_baselines"
    __table_args__ = (
        Index("ix_benchmark_baseline_suite", "benchmark_suite_id"),
        UniqueConstraint(
            "organization_id",
            "benchmark_suite_id",
            "metric_name",
            name="uq_benchmark_baseline_suite_metric",
        ),
    )

    benchmark_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_suites.id", ondelete="CASCADE"), index=True
    )
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    baseline_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["BenchmarkBaseline"]
