"""SLO/SLI compliance results."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import SliType


class SloResult(BaseModel):
    """``slo_results`` -- one evaluation of a named SLO against its own
    target."""

    __tablename__ = "slo_results"
    __table_args__ = (Index("ix_slo_result_name", "slo_name"),)

    slo_name: Mapped[str] = mapped_column(String(256), index=True)
    sli_type: Mapped[SliType] = mapped_column(String(24), index=True)
    target_value: Mapped[float] = mapped_column(Float)
    actual_value: Mapped[float] = mapped_column(Float)
    is_compliant: Mapped[bool] = mapped_column(Boolean, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["SloResult"]
