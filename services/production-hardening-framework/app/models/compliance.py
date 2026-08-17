"""Compliance validation results."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ComplianceFramework


class ComplianceResult(BaseModel):
    """``compliance_results`` -- one control's own evaluation against
    a compliance framework."""

    __tablename__ = "compliance_results"

    framework: Mapped[ComplianceFramework] = mapped_column(String(16), index=True)
    control_id: Mapped[str] = mapped_column(String(64), index=True)
    is_compliant: Mapped[bool] = mapped_column(Boolean, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["ComplianceResult"]
