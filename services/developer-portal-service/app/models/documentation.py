"""Documentation pages, their version history, and reader feedback."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ContentStatus, FeedbackSentiment


class DocumentationPage(BaseModel):
    """``documentation_pages`` -- one published (or draft) documentation
    page."""

    __tablename__ = "documentation_pages"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_documentation_page_slug"),
        Index("ix_documentation_page_status", "status"),
    )

    slug: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.DRAFT, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class DocumentationVersion(BaseModel):
    """``documentation_versions`` -- one historical snapshot of a
    documentation page's content."""

    __tablename__ = "documentation_versions"
    __table_args__ = (Index("ix_documentation_version_page", "documentation_page_id"),)

    documentation_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documentation_pages.id", ondelete="CASCADE"), index=True
    )
    version_label: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentationFeedback(BaseModel):
    """``documentation_feedback`` -- one reader's helpful/not-helpful
    feedback on a documentation page."""

    __tablename__ = "documentation_feedback"
    __table_args__ = (Index("ix_documentation_feedback_page", "documentation_page_id"),)

    documentation_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documentation_pages.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    sentiment: Mapped[FeedbackSentiment] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text, default="")


__all__ = ["DocumentationFeedback", "DocumentationPage", "DocumentationVersion"]
