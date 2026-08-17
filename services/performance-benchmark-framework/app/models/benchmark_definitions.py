"""Benchmark suites and the load profiles they run under."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import BenchmarkType, LoadProfile


class BenchmarkSuite(BaseModel):
    """``benchmark_suites`` -- one named collection of benchmark runs."""

    __tablename__ = "benchmark_suites"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_benchmark_suite_name"),)

    name: Mapped[str] = mapped_column(String(256), index=True)
    benchmark_type: Mapped[BenchmarkType] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class BenchmarkProfile(BaseModel):
    """``benchmark_profiles`` -- one named load shape a benchmark run can
    be driven with."""

    __tablename__ = "benchmark_profiles"
    __table_args__ = (Index("ix_benchmark_profile_suite", "benchmark_suite_id"),)

    benchmark_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_suites.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    load_profile: Mapped[LoadProfile] = mapped_column(String(16), index=True)
    concurrency: Mapped[int] = mapped_column(Integer, default=1)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=60)


__all__ = ["BenchmarkProfile", "BenchmarkSuite"]
