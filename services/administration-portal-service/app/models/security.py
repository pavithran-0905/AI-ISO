"""Security policy settings and security events."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import SecurityEventKind, SecurityEventSeverity


class SecuritySetting(BaseModel):
    """``security_settings`` -- one named security policy (password,
    session, MFA, IP restrictions)."""

    __tablename__ = "security_settings"
    __table_args__ = (Index("ix_security_setting_key", "key"),)

    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class SecurityEvent(BaseModel):
    """``security_events`` -- one detected security-relevant event."""

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_event_kind", "kind"),
        Index("ix_security_event_severity", "severity"),
        Index("ix_security_event_detected_at", "detected_at"),
    )

    kind: Mapped[SecurityEventKind] = mapped_column(String(32), index=True)
    severity: Mapped[SecurityEventSeverity] = mapped_column(String(8), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


__all__ = ["SecurityEvent", "SecuritySetting"]
