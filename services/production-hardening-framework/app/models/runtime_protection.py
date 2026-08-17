"""Runtime protection events."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import FindingSeverity, RuntimeProtectionEventType


class RuntimeProtectionEvent(BaseModel):
    """``runtime_protection`` -- one detected runtime protection
    event."""

    __tablename__ = "runtime_protection"

    event_type: Mapped[RuntimeProtectionEventType] = mapped_column(String(24), index=True)
    severity: Mapped[FindingSeverity] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["RuntimeProtectionEvent"]
