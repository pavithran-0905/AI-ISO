"""Platform settings, system configuration, and feature flags."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import FeatureFlagScope

MAX_ROLLOUT_PERCENTAGE = 100.0


class PlatformSetting(BaseModel):
    """``platform_settings`` -- one global platform setting."""

    __tablename__ = "platform_settings"
    __table_args__ = (Index("ix_platform_setting_key", "key"),)

    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    description: Mapped[str | None] = mapped_column(String(512), default=None)


class SystemConfiguration(BaseModel):
    """``system_configuration`` -- one runtime configuration entry.

    History is the entry's own append-only trail on ``system_audit``
    (every change routes through ``AuditService``, per this service's
    single-write-path discipline) rather than a second, separately
    maintained history table -- there is exactly one place a
    configuration change can be recorded, so there is exactly one place
    it can be looked up.
    """

    __tablename__ = "system_configuration"
    __table_args__ = (Index("ix_system_configuration_key", "key"),)

    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    environment: Mapped[str] = mapped_column(String(32), default="production")
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)


class FeatureFlag(BaseModel):
    """``feature_flags`` -- one feature flag, at any scope."""

    __tablename__ = "feature_flags"
    __table_args__ = (
        Index("ix_feature_flag_name", "name"),
        Index("ix_feature_flag_scope", "scope"),
    )

    name: Mapped[str] = mapped_column(String(128), index=True)
    scope: Mapped[FeatureFlagScope] = mapped_column(String(16), index=True)
    target_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    """The tenant/organization/project id this flag targets -- ``None``
    for a ``GLOBAL`` flag."""
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_killed: Mapped[bool] = mapped_column(Boolean, default=False)
    """A kill switch always evaluates ``False`` regardless of
    ``is_enabled``/rollout -- a distinct, higher-priority override for
    an emergency disable, never conflated with the ordinary toggle."""
    rollout_percentage: Mapped[float] = mapped_column(Float, default=MAX_ROLLOUT_PERCENTAGE)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    depends_on_flag_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_flags.id", ondelete="SET NULL"), default=None
    )
    min_platform_version: Mapped[str | None] = mapped_column(String(32), default=None)
    max_platform_version: Mapped[str | None] = mapped_column(String(32), default=None)


__all__ = ["FeatureFlag", "PlatformSetting", "SystemConfiguration"]
