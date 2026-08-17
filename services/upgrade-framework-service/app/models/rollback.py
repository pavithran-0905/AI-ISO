"""Rollback history for upgrade jobs run by this framework."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import UpgradeJobStatus


class RollbackHistory(BaseModel):
    """``rollback_history`` -- one rollback attempt for an upgrade
    job."""

    __tablename__ = "rollback_history"
    __table_args__ = (Index("ix_rollback_history_job", "upgrade_job_id"),)

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[UpgradeJobStatus] = mapped_column(
        String(16), default=UpgradeJobStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["RollbackHistory"]
