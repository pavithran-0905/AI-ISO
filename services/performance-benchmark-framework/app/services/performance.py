"""Performance profiles and the raw metric points collected against
them."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import BenchmarkType
from app.models.performance import PerformanceMetric, PerformanceProfile
from app.repositories.performance import PerformanceMetricRepository, PerformanceProfileRepository


class PerformanceProfileService:
    def __init__(self, repo: PerformanceProfileRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, name: str, target_type: BenchmarkType
    ) -> PerformanceProfile:
        return await self._repo.create(
            PerformanceProfile(organization_id=organization_id, name=name, target_type=target_type)
        )


class PerformanceMetricService:
    def __init__(self, repo: PerformanceMetricRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        performance_profile_id: UUID,
        metric_name: str,
        value: float,
        unit: str = "",
        recorded_at: datetime,
    ) -> PerformanceMetric:
        return await self._repo.create(
            PerformanceMetric(
                organization_id=organization_id,
                performance_profile_id=performance_profile_id,
                metric_name=metric_name,
                value=value,
                unit=unit,
                recorded_at=recorded_at,
            )
        )


__all__ = ["PerformanceMetricService", "PerformanceProfileService"]
