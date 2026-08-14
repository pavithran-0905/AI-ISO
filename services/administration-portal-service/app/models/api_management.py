"""API keys and their per-window usage rollup.

**``ApiKey.key_hash`` is a hash, never the raw key.** The raw key is
shown to the caller exactly once at creation and never persisted or
retrievable again -- the same discipline every credential-issuing
AI-IOS service follows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ApiKeyStatus


class ApiKey(BaseModel):
    """``api_keys`` -- one issued administrative API key."""

    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_api_key_status", "status"),)

    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[ApiKeyStatus] = mapped_column(
        String(16), default=ApiKeyStatus.ACTIVE, index=True
    )
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, default=None)
    quota_limit: Mapped[float | None] = mapped_column(Float, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ApiUsage(BaseModel):
    """``api_usage`` -- one idempotent per-window request-count rollup
    for an API key."""

    __tablename__ = "api_usage"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "api_key_id", "window_start", name="uq_api_usage_window"
        ),
        Index("ix_api_usage_api_key", "api_key_id"),
    )

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"), index=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, default=0)


__all__ = ["ApiKey", "ApiUsage"]
