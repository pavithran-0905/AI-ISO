"""Release channels and the versions published to them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ReleaseChannelType


class ReleaseChannel(BaseModel):
    """``release_channels`` -- one named distribution channel (stable,
    LTS, beta, canary, a custom enterprise/regional/private channel)."""

    __tablename__ = "release_channels"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_release_channel_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    channel_type: Mapped[ReleaseChannelType] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ReleaseVersion(BaseModel):
    """``release_versions`` -- one platform release published to a
    channel."""

    __tablename__ = "release_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "release_channel_id",
            "version_label",
            name="uq_release_version_label",
        ),
        Index("ix_release_version_channel", "release_channel_id"),
    )

    release_channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_channels.id", ondelete="CASCADE"), index=True
    )
    version_label: Mapped[str] = mapped_column(String(32), index=True)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="")
    artifact_ref: Mapped[str] = mapped_column(String(512), default="")


__all__ = ["ReleaseChannel", "ReleaseVersion"]
