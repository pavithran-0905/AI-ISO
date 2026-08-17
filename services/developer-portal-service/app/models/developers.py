"""Developer profiles, portal sessions, bookmarks, and favorites."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DeveloperSessionStatus, SearchContentType


class DeveloperProfile(BaseModel):
    """``developer_profiles`` -- one developer's portal profile."""

    __tablename__ = "developer_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_developer_profile_user"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    """The developer's identifier, as carried by their own verified
    token -- a cross-service reference, never a foreign key, matching
    every other AI-IOS service's convention for identities another
    service owns."""
    display_name: Mapped[str] = mapped_column(String(128), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)


class DeveloperSession(BaseModel):
    """``developer_sessions`` -- one portal session for a developer."""

    __tablename__ = "developer_sessions"
    __table_args__ = (
        Index("ix_developer_session_user", "user_id"),
        Index("ix_developer_session_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[DeveloperSessionStatus] = mapped_column(
        String(16), default=DeveloperSessionStatus.ACTIVE, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class DeveloperBookmark(BaseModel):
    """``developer_bookmarks`` -- one piece of content a developer has
    bookmarked for later."""

    __tablename__ = "developer_bookmarks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "content_type",
            "content_id",
            name="uq_developer_bookmark",
        ),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    content_type: Mapped[SearchContentType] = mapped_column(String(16), index=True)
    content_id: Mapped[uuid.UUID] = mapped_column(index=True)


class DeveloperFavorite(BaseModel):
    """``developer_favorites`` -- one piece of content a developer has
    marked as a favorite."""

    __tablename__ = "developer_favorites"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "content_type",
            "content_id",
            name="uq_developer_favorite",
        ),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    content_type: Mapped[SearchContentType] = mapped_column(String(16), index=True)
    content_id: Mapped[uuid.UUID] = mapped_column(index=True)


__all__ = ["DeveloperBookmark", "DeveloperFavorite", "DeveloperProfile", "DeveloperSession"]
