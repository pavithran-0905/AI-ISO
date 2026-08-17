"""SDK download tracking, as observed through the portal's own SDK
center (distinct from ``services/sdk-cli-service``'s own
``sdk_downloads`` table, which tracks downloads at the SDK-artifact
level; this one tracks the portal experience of downloading one)."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class SdkDownload(BaseModel):
    """``sdk_downloads`` -- one SDK download initiated through the
    portal's SDK center."""

    __tablename__ = "sdk_downloads"
    __table_args__ = (
        Index("ix_portal_sdk_download_user", "user_id"),
        Index("ix_portal_sdk_download_language", "language"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    language: Mapped[str] = mapped_column(String(16), index=True)
    version_label: Mapped[str] = mapped_column(String(32))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["SdkDownload"]
