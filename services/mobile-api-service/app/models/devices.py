"""Mobile devices, sessions, profiles, and device-bound tokens."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    DeviceTrustStatus,
    MobileAuthMethod,
    MobilePlatform,
    SessionStatus,
    TokenStatus,
)


class MobileDevice(BaseModel):
    """``mobile_devices`` -- one enrolled mobile device."""

    __tablename__ = "mobile_devices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "device_identifier", name="uq_mobile_device_identifier"
        ),
        Index("ix_mobile_device_trust_status", "trust_status"),
    )

    device_identifier: Mapped[str] = mapped_column(String(255), index=True)
    """The client-generated stable device identifier -- never the raw
    hardware serial, per the platform's device-privacy conventions."""
    platform: Mapped[MobilePlatform] = mapped_column(String(16), index=True)
    device_model: Mapped[str | None] = mapped_column(String(128), default=None)
    os_version: Mapped[str | None] = mapped_column(String(64), default=None)
    app_version_label: Mapped[str | None] = mapped_column(String(32), default=None)
    """Deliberately not named ``version`` -- that is already
    ``BaseEntityMixin``'s own reserved optimistic-locking column (a
    plain integer every ``BaseRepository.update()`` increments), and a
    domain-level version *string* silently colliding with it is exactly
    the class of defect ``services/sdk-cli-service`` found and
    documented in Prompt 071."""
    trust_status: Mapped[DeviceTrustStatus] = mapped_column(
        String(16), default=DeviceTrustStatus.PENDING, index=True
    )
    is_jailbroken: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rooted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class MobileSession(BaseModel):
    """``mobile_sessions`` -- one authenticated session bound to one
    device."""

    __tablename__ = "mobile_sessions"
    __table_args__ = (
        Index("ix_mobile_session_device", "device_id"),
        Index("ix_mobile_session_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    """The authenticated user's identifier, as carried by the caller's
    own verified token -- a cross-service reference, never a foreign
    key, matching every other AI-IOS service's convention for
    identities another service owns."""
    auth_method: Mapped[MobileAuthMethod] = mapped_column(String(24))
    status: Mapped[SessionStatus] = mapped_column(
        String(16), default=SessionStatus.ACTIVE, index=True
    )
    is_new_device: Mapped[bool] = mapped_column(Boolean, default=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class MobileProfile(BaseModel):
    """``mobile_profiles`` -- one user's mobile-specific profile and
    preferences."""

    __tablename__ = "mobile_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_mobile_profile_user"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    locale: Mapped[str] = mapped_column(String(16), default="en-US")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    preferences: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class MobileToken(BaseModel):
    """``mobile_tokens`` -- one device-bound offline/refresh token this
    service itself issues and tracks (distinct from the platform's own
    authentication-service-issued JWTs)."""

    __tablename__ = "mobile_tokens"
    __table_args__ = (
        Index("ix_mobile_token_device", "device_id"),
        Index("ix_mobile_token_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[TokenStatus] = mapped_column(String(16), default=TokenStatus.ACTIVE, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["MobileDevice", "MobileProfile", "MobileSession", "MobileToken"]
