"""Individual download events for release artifacts."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class DownloadStatistic(BaseModel):
    """``download_statistics`` -- one recorded download of a release
    artifact."""

    __tablename__ = "download_statistics"
    __table_args__ = (Index("ix_download_statistic_artifact", "release_artifact_id"),)

    release_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_artifacts.id", ondelete="CASCADE"), index=True
    )
    region_code: Mapped[str] = mapped_column(String(16), default="")
    bytes_transferred: Mapped[int] = mapped_column(BigInteger, default=0)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["DownloadStatistic"]
