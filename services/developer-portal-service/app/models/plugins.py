"""Plugin submissions and their reviewer decisions (integrating
Prompt 059's marketplace as the eventual publication target)."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import PluginReviewDecision, PluginSubmissionStatus


class PluginSubmission(BaseModel):
    """``plugin_submissions`` -- one developer's plugin publishing
    submission."""

    __tablename__ = "plugin_submissions"
    __table_args__ = (
        Index("ix_plugin_submission_user", "user_id"),
        Index("ix_plugin_submission_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    plugin_name: Mapped[str] = mapped_column(String(128))
    version_label: Mapped[str] = mapped_column(String(32))
    """Deliberately not named ``version`` -- see
    ``services/sdk-cli-service``'s and ``services/public-api-platform``'s
    own documented lesson on this exact collision with
    ``BaseEntityMixin``'s reserved optimistic-locking column."""
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[PluginSubmissionStatus] = mapped_column(
        String(24), default=PluginSubmissionStatus.SUBMITTED, index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    marketplace_ref: Mapped[str | None] = mapped_column(String(256), default=None)
    """Cross-service reference to ``services/plugin-marketplace-service``'s
    own catalog entry once published -- never a foreign key, matching
    every other AI-IOS service's convention for identities another
    service owns."""


class PluginReview(BaseModel):
    """``plugin_reviews`` -- one reviewer's decision on a plugin
    submission."""

    __tablename__ = "plugin_reviews"
    __table_args__ = (Index("ix_plugin_review_submission", "plugin_submission_id"),)

    plugin_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugin_submissions.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(128))
    decision: Mapped[PluginReviewDecision] = mapped_column(String(24))
    comments: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = ["PluginReview", "PluginSubmission"]
