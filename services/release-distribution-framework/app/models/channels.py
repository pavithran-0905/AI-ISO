"""Release channel definitions -- the named, configurable channels
release versions move through."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ReleaseChannelType


class ReleaseChannelConfig(BaseModel):
    """``release_channels`` -- one named, configurable release
    channel."""

    __tablename__ = "release_channels"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_release_channel_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    channel_type: Mapped[ReleaseChannelType] = mapped_column(String(24), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["ReleaseChannelConfig"]
