"""Release promotions -- the audited record of a release version
moving between channels."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import PromotionStatus, ReleaseChannelType


class ReleasePromotion(BaseModel):
    """``release_promotions`` -- one release version's own promotion
    from one channel to another."""

    __tablename__ = "release_promotions"
    __table_args__ = (
        Index("ix_release_promotion_version", "release_version_id"),
        Index("ix_release_promotion_status", "status"),
    )

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    from_channel_type: Mapped[ReleaseChannelType] = mapped_column(String(24))
    to_channel_type: Mapped[ReleaseChannelType] = mapped_column(String(24))
    status: Mapped[PromotionStatus] = mapped_column(
        String(16), default=PromotionStatus.PENDING, index=True
    )
    approved_by: Mapped[str] = mapped_column(String(128), default="")
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["ReleasePromotion"]
