"""Mobile app version policy and remote configuration."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import MobilePlatform, ReleaseChannel


class MobileAppVersion(BaseModel):
    """``mobile_app_versions`` -- one platform's current version policy:
    what is out, what is merely recommended, and what is mandatory."""

    __tablename__ = "mobile_app_versions"
    __table_args__ = (
        Index("ix_mobile_app_version_platform", "platform"),
        Index("ix_mobile_app_version_label", "version_label"),
    )

    platform: Mapped[MobilePlatform] = mapped_column(String(16), index=True)
    version_label: Mapped[str] = mapped_column(String(32), index=True)
    """Deliberately not named ``version`` -- see
    ``MobileDevice.app_version_label`` for why."""
    release_channel: Mapped[ReleaseChannel] = mapped_column(
        String(8), default=ReleaseChannel.STABLE, index=True
    )
    minimum_version_label: Mapped[str] = mapped_column(String(32))
    recommended_version_label: Mapped[str] = mapped_column(String(32))
    is_forced_upgrade: Mapped[bool] = mapped_column(Boolean, default=False)
    release_notes: Mapped[str] = mapped_column(String(4096), default="")
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MobileConfiguration(BaseModel):
    """``mobile_configuration`` -- one remote configuration entry, keyed
    within its own environment and optional platform scope."""

    __tablename__ = "mobile_configuration"
    __table_args__ = (
        Index("ix_mobile_configuration_key", "key"),
        Index("ix_mobile_configuration_environment", "environment"),
    )

    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    environment: Mapped[str] = mapped_column(String(32), default="production", index=True)
    platform: Mapped[MobilePlatform | None] = mapped_column(String(16), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rollback_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mobile_configuration.id", ondelete="SET NULL"), default=None
    )


__all__ = ["MobileAppVersion", "MobileConfiguration"]
