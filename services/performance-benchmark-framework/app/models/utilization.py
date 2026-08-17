"""Point-in-time resource utilization samples."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ResourceType


class ResourceUtilization(BaseModel):
    """``resource_utilization`` -- one point-in-time utilization sample
    for a tracked resource."""

    __tablename__ = "resource_utilization"
    __table_args__ = (Index("ix_resource_utilization_type", "resource_type"),)

    resource_type: Mapped[ResourceType] = mapped_column(String(24), index=True)
    utilization_percent: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["ResourceUtilization"]
