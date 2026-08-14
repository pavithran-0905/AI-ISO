"""Administrator sessions and administrative actions.

**Distinct from ``system_audit``.** ``AdminAction`` is this service's
own operational log of session-level administrative operations (force
logout, password reset, session revocation); ``system_audit``
(`app/models/reporting.py`) is the platform-wide immutable trail
docs/070's own AUDIT section names. Two different retention/query
shapes for two different questions -- "what did this admin session do"
versus "what happened to the platform."
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class AdminSession(BaseModel):
    """``admin_sessions`` -- one administrator session."""

    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_session_admin_user", "admin_user_id"),)

    admin_user_id: Mapped[str] = mapped_column(String(128), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    """Whether this session is still usable -- ``False`` once force
    logged out, deliberately not named ``is_active`` (see this
    package's README on ``BaseEntityMixin``'s own reserved columns)."""


class AdminAction(BaseModel):
    """``admin_actions`` -- one administrative operation performed
    within a session."""

    __tablename__ = "admin_actions"
    __table_args__ = (
        Index("ix_admin_action_admin_user", "admin_user_id"),
        Index("ix_admin_action_performed_at", "performed_at"),
    )

    admin_user_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


__all__ = ["AdminAction", "AdminSession"]
