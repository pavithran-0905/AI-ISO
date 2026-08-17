"""Hardening runs and the per-check results within them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CheckResultStatus, HardeningRunStatus


class HardeningRun(BaseModel):
    """``hardening_runs`` -- one execution of a hardening profile -- see
    ``app.hardening.engine`` for the transition table this drives."""

    __tablename__ = "hardening_runs"
    __table_args__ = (
        Index("ix_hardening_run_profile", "hardening_profile_id"),
        Index("ix_hardening_run_status", "status"),
    )

    hardening_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hardening_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[HardeningRunStatus] = mapped_column(
        String(16), default=HardeningRunStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")


class HardeningResult(BaseModel):
    """``hardening_results`` -- one individual check's own outcome
    within a hardening run."""

    __tablename__ = "hardening_results"
    __table_args__ = (Index("ix_hardening_result_run", "hardening_run_id"),)

    hardening_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hardening_runs.id", ondelete="CASCADE"), index=True
    )
    check_name: Mapped[str] = mapped_column(String(256), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["HardeningResult", "HardeningRun"]
