"""Tutorials and multi-tutorial learning paths."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ContentStatus, TutorialDifficulty


class Tutorial(BaseModel):
    """``tutorials`` -- one published (or draft) tutorial."""

    __tablename__ = "tutorials"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_tutorial_slug"),
        Index("ix_tutorial_status", "status"),
    )

    slug: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[TutorialDifficulty] = mapped_column(
        String(16), default=TutorialDifficulty.BEGINNER
    )
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.DRAFT, index=True
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class LearningPath(BaseModel):
    """``learning_paths`` -- one ordered sequence of tutorials."""

    __tablename__ = "learning_paths"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_learning_path_slug"),
        Index("ix_learning_path_status", "status"),
    )

    slug: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    tutorial_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.DRAFT, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["LearningPath", "Tutorial"]
