"""Coverage reports."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CoverageType


class CoverageReport(BaseModel):
    """``coverage_reports`` -- one coverage measurement, optionally
    tied to the test run that produced it."""

    __tablename__ = "coverage_reports"
    __table_args__ = (Index("ix_coverage_report_run", "test_run_id"),)

    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), default=None, index=True
    )
    coverage_type: Mapped[CoverageType] = mapped_column(String(16), index=True)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    lines_covered: Mapped[int] = mapped_column(Integer, default=0)
    lines_total: Mapped[int] = mapped_column(Integer, default=0)


__all__ = ["CoverageReport"]
