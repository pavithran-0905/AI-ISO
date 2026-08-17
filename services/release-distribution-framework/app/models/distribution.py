"""Release distributions and the regions they target."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DistributionStatus, DistributionType


class ReleaseDistribution(BaseModel):
    """``release_distributions`` -- one distribution of a release
    version to one target."""

    __tablename__ = "release_distributions"
    __table_args__ = (Index("ix_release_distribution_version", "release_version_id"),)

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    distribution_type: Mapped[DistributionType] = mapped_column(String(24), index=True)
    status: Mapped[DistributionStatus] = mapped_column(
        String(16), default=DistributionStatus.PENDING, index=True
    )
    target: Mapped[str] = mapped_column(String(256), default="")
    distributed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ReleaseRegion(BaseModel):
    """``release_regions`` -- one geographic distribution region."""

    __tablename__ = "release_regions"

    name: Mapped[str] = mapped_column(String(128), index=True)
    region_code: Mapped[str] = mapped_column(String(16), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["ReleaseDistribution", "ReleaseRegion"]
