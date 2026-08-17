"""Release versions -- the central entity every other table in this
service hangs off."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ReleaseStatus


class ReleaseVersion(BaseModel):
    """``release_versions`` -- one named, versioned release -- see
    ``app.release.engine`` for the transition table this drives."""

    __tablename__ = "release_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "version_label", name="uq_release_version_label"),
        Index("ix_release_version_channel", "release_channel_id"),
    )

    version_label: Mapped[str] = mapped_column(String(64), index=True)
    release_channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_channels.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[ReleaseStatus] = mapped_column(
        String(16), default=ReleaseStatus.DRAFT, index=True
    )
    is_security_release: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["ReleaseVersion"]
