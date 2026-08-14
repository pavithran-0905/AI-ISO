"""Statistics rollup: idempotent per-window aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.reporting import EdgeStatistic
from app.repositories.reporting import EdgeStatisticRepository


class StatisticsService:
    """Rolls up one organization's fleet counts for one window,
    idempotently."""

    def __init__(self, repo: EdgeStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        sites_registered: int,
        devices_online: int,
        devices_offline: int,
        synchronizations_completed: int,
        synchronizations_failed: int,
        updates_completed: int,
        updates_failed: int,
    ) -> EdgeStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is None:
            existing = EdgeStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.window_end = window_end
        existing.sites_registered = sites_registered
        existing.devices_online = devices_online
        existing.devices_offline = devices_offline
        existing.synchronizations_completed = synchronizations_completed
        existing.synchronizations_failed = synchronizations_failed
        existing.updates_completed = updates_completed
        existing.updates_failed = updates_failed
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
