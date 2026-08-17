"""Installation sessions and their log lines."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import InstallationMode, InstallationSessionStatus


class InstallationSession(BaseModel):
    """``installation_sessions`` -- one platform installation attempt --
    see ``app.installer.engine`` for the transition table this drives."""

    __tablename__ = "installation_sessions"
    __table_args__ = (Index("ix_installation_session_status", "status"),)

    mode: Mapped[InstallationMode] = mapped_column(String(24), index=True)
    status: Mapped[InstallationSessionStatus] = mapped_column(
        String(16), default=InstallationSessionStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None)


class InstallationLog(BaseModel):
    """``installation_logs`` -- one log line emitted during an
    installation session."""

    __tablename__ = "installation_logs"
    __table_args__ = (Index("ix_installation_log_session", "installation_session_id"),)

    installation_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("installation_sessions.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["InstallationLog", "InstallationSession"]
