"""Capacity models (a resource's own tracked growth) and the forecasts
computed from them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ResourceType


class CapacityModel(BaseModel):
    """``capacity_models`` -- one resource's own tracked growth rate,
    used to project future capacity."""

    __tablename__ = "capacity_models"
    __table_args__ = (Index("ix_capacity_model_resource_type", "resource_type"),)

    name: Mapped[str] = mapped_column(String(256), index=True)
    resource_type: Mapped[ResourceType] = mapped_column(String(24), index=True)
    growth_rate_percent: Mapped[float] = mapped_column(Float)


class CapacityForecast(BaseModel):
    """``capacity_forecasts`` -- one projected future value for a
    capacity model, and the threshold it is measured against."""

    __tablename__ = "capacity_forecasts"
    __table_args__ = (Index("ix_capacity_forecast_model", "capacity_model_id"),)

    capacity_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capacity_models.id", ondelete="CASCADE"), index=True
    )
    forecast_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    projected_value: Mapped[float] = mapped_column(Float)
    threshold_value: Mapped[float] = mapped_column(Float)


__all__ = ["CapacityForecast", "CapacityModel"]
