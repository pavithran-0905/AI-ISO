"""Release builds -- the build-provenance record behind each release
version."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import BuildStatus


class ReleaseBuild(BaseModel):
    """``release_builds`` -- one build attempt for a release version,
    carrying build provenance -- see ``app.release_build.engine`` for the
    transition table this drives."""

    __tablename__ = "release_builds"
    __table_args__ = (
        Index("ix_release_build_version", "release_version_id"),
        Index("ix_release_build_status", "status"),
    )

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[BuildStatus] = mapped_column(String(16), default=BuildStatus.PENDING, index=True)
    source_commit: Mapped[str] = mapped_column(String(64), default="")
    builder_identity: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")


__all__ = ["ReleaseBuild"]
