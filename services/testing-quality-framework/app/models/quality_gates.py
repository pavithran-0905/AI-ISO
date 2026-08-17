"""Quality gates -- named, thresholded release criteria."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import QualityGateStatus, QualityGateType


class QualityGate(BaseModel):
    """``quality_gates`` -- one named release criterion (minimum
    coverage, a performance threshold, security validation, and so
    on) and its own most recently evaluated outcome."""

    __tablename__ = "quality_gates"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_quality_gate_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    gate_type: Mapped[QualityGateType] = mapped_column(String(32), index=True)
    threshold: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[QualityGateStatus] = mapped_column(
        String(16), default=QualityGateStatus.PENDING, index=True
    )
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["QualityGate"]
