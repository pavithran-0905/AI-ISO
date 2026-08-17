"""LTS lifecycle tracking and end-of-life scheduling."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column


class LtsVersion(BaseModel):
    """``lts_versions`` -- one release version's own long-term-support
    tracking."""

    __tablename__ = "lts_versions"
    __table_args__ = (Index("ix_lts_version_release", "release_version_id"),)

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    support_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    support_expiry_notice_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    """Set once support-expiry has first entered its own warning
    window -- the edge-trigger flag
    ``LtsSupportExpirySweepWorker`` uses so a long-neglected LTS line
    does not re-notify on every tick."""


class EolSchedule(BaseModel):
    """``eol_schedule`` -- one release version's own end-of-life
    schedule."""

    __tablename__ = "eol_schedule"
    __table_args__ = (Index("ix_eol_schedule_release", "release_version_id"),)

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    eol_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    migration_recommendation: Mapped[str] = mapped_column(Text, default="")
    deprecation_notice_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    """Set once EOL has first entered its own warning window -- the
    edge-trigger flag ``EolScheduleSweepWorker`` uses so a
    long-scheduled EOL does not re-notify on every tick."""


__all__ = ["EolSchedule", "LtsVersion"]
