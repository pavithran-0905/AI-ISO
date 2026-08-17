"""Capacity models and the forecasts computed from them."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.capacity import CapacityForecast, CapacityModel
from app.models.enums import ResourceType
from app.repositories.capacity import CapacityForecastRepository, CapacityModelRepository


class CapacityModelService:
    def __init__(self, repo: CapacityModelRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        resource_type: ResourceType,
        growth_rate_percent: float,
    ) -> CapacityModel:
        return await self._repo.create(
            CapacityModel(
                organization_id=organization_id,
                name=name,
                resource_type=resource_type,
                growth_rate_percent=growth_rate_percent,
            )
        )


class CapacityForecastService:
    def __init__(self, repo: CapacityForecastRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        capacity_model_id: UUID,
        forecast_date: datetime,
        projected_value: float,
        threshold_value: float,
    ) -> CapacityForecast:
        return await self._repo.create(
            CapacityForecast(
                organization_id=organization_id,
                capacity_model_id=capacity_model_id,
                forecast_date=forecast_date,
                projected_value=projected_value,
                threshold_value=threshold_value,
            )
        )


__all__ = ["CapacityForecastService", "CapacityModelService"]
