"""Security test results and chaos engineering results."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ChaosFaultType, CheckResultStatus, SecurityTestType


class SecurityResult(BaseModel):
    """``security_results`` -- one security test's own outcome,
    optionally tied to the test run that produced it."""

    __tablename__ = "security_results"
    __table_args__ = (Index("ix_security_result_run", "test_run_id"),)

    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), default=None, index=True
    )
    security_type: Mapped[SecurityTestType] = mapped_column(String(24), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")


class ChaosResult(BaseModel):
    """``chaos_results`` -- one chaos experiment's own outcome,
    optionally tied to the test run that produced it."""

    __tablename__ = "chaos_results"
    __table_args__ = (Index("ix_chaos_result_run", "test_run_id"),)

    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), default=None, index=True
    )
    fault_type: Mapped[ChaosFaultType] = mapped_column(String(24), index=True)
    recovery_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["ChaosResult", "SecurityResult"]
