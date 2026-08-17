"""Community discussion posts and comments."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CommunityPostStatus, CommunityPostType, ModerationStatus


class CommunityPost(BaseModel):
    """``community_posts`` -- one discussion board question or
    discussion thread."""

    __tablename__ = "community_posts"
    __table_args__ = (
        Index("ix_community_post_user", "user_id"),
        Index("ix_community_post_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    post_type: Mapped[CommunityPostType] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[CommunityPostStatus] = mapped_column(
        String(16), default=CommunityPostStatus.OPEN, index=True
    )
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        String(16), default=ModerationStatus.VISIBLE, index=True
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    accepted_comment_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class CommunityComment(BaseModel):
    """``community_comments`` -- one comment on a community post."""

    __tablename__ = "community_comments"
    __table_args__ = (Index("ix_community_comment_post", "community_post_id"),)

    community_post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("community_posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    body: Mapped[str] = mapped_column(Text)
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        String(16), default=ModerationStatus.VISIBLE, index=True
    )
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = ["CommunityComment", "CommunityPost"]
