"""Release notes."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ReleaseNoteType


class ReleaseNote(BaseModel):
    """``release_notes`` -- one documented change entry for a release
    version."""

    __tablename__ = "release_notes"
    __table_args__ = (Index("ix_release_note_version", "release_version_id"),)

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    note_type: Mapped[ReleaseNoteType] = mapped_column(String(24), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["ReleaseNote"]
