"""Detected performance regressions."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import RegressionSeverity, RegressionType


class PerformanceRegression(BaseModel):
    """``performance_regressions`` -- one detected regression against a
    metric's own baseline."""

    __tablename__ = "performance_regressions"
    __table_args__ = (Index("ix_performance_regression_type", "regression_type"),)

    regression_type: Mapped[RegressionType] = mapped_column(String(16), index=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    baseline_value: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float)
    regression_percent: Mapped[float] = mapped_column(Float)
    severity: Mapped[RegressionSeverity] = mapped_column(String(16), index=True)


__all__ = ["PerformanceRegression"]
