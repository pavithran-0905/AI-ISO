"""Statistics rollup: idempotent per-window aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.reporting import SystemStatistic
from app.repositories.reporting import SystemStatisticRepository


class StatisticsService:
    """Rolls up one organization's platform counts for one window,
    idempotently."""

    def __init__(self, repo: SystemStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        tenant_count: int,
        user_count: int,
        api_request_count: int,
        background_job_count: int,
        security_event_count: int,
        platform_availability_fraction: float | None,
    ) -> SystemStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is None:
            existing = SystemStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.window_end = window_end
        existing.tenant_count = tenant_count
        existing.user_count = user_count
        existing.api_request_count = api_request_count
        existing.background_job_count = background_job_count
        existing.security_event_count = security_event_count
        existing.platform_availability_fraction = platform_availability_fraction
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
