"""Pre-flight infrastructure checks and dependency compatibility checks."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CheckResultStatus, PreflightCheckType


class PreflightResult(BaseModel):
    """``preflight_results`` -- one infrastructure readiness check
    outcome, optionally tied to an installation session."""

    __tablename__ = "preflight_results"
    __table_args__ = (
        Index("ix_preflight_result_session", "installation_session_id"),
        Index("ix_preflight_result_check_type", "check_type"),
    )

    installation_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("installation_sessions.id", ondelete="CASCADE"), default=None, index=True
    )
    check_type: Mapped[PreflightCheckType] = mapped_column(String(32), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DependencyCheck(BaseModel):
    """``dependency_checks`` -- one dependency version-compatibility
    check outcome, optionally tied to an installation session."""

    __tablename__ = "dependency_checks"
    __table_args__ = (Index("ix_dependency_check_session", "installation_session_id"),)

    installation_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("installation_sessions.id", ondelete="CASCADE"), default=None, index=True
    )
    dependency_name: Mapped[str] = mapped_column(String(128), index=True)
    required_version: Mapped[str] = mapped_column(String(32))
    found_version: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["DependencyCheck", "PreflightResult"]
