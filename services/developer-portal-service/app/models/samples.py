"""Sample projects and their reusable code snippets."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ContentStatus, SampleProjectCategory


class SampleProject(BaseModel):
    """``sample_projects`` -- one reference application, starter
    template, or example integration."""

    __tablename__ = "sample_projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_sample_project_slug"),
        Index("ix_sample_project_category", "category"),
        Index("ix_sample_project_status", "status"),
    )

    slug: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[SampleProjectCategory] = mapped_column(String(16), index=True)
    repository_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.DRAFT, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CodeSnippet(BaseModel):
    """``code_snippets`` -- one reusable code snippet, optionally
    attached to a sample project."""

    __tablename__ = "code_snippets"
    __table_args__ = (Index("ix_code_snippet_sample_project", "sample_project_id"),)

    sample_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sample_projects.id", ondelete="CASCADE"), default=None
    )
    title: Mapped[str] = mapped_column(String(256))
    language: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")


__all__ = ["CodeSnippet", "SampleProject"]
