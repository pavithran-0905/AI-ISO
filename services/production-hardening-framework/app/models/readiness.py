"""Operational readiness and disaster recovery validation checks."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    CheckResultStatus,
    DisasterRecoveryCheckType,
    OperationalReadinessCheckType,
)


class OperationalReadiness(BaseModel):
    """``operational_readiness`` -- one operational readiness check's
    own latest outcome."""

    __tablename__ = "operational_readiness"

    check_type: Mapped[OperationalReadinessCheckType] = mapped_column(String(16), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DisasterRecoveryCheck(BaseModel):
    """``disaster_recovery_checks`` -- one disaster recovery
    validation's own latest outcome."""

    __tablename__ = "disaster_recovery_checks"

    check_type: Mapped[DisasterRecoveryCheckType] = mapped_column(String(24), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["DisasterRecoveryCheck", "OperationalReadiness"]
