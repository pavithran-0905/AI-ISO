"""Statistics rollup: idempotent per-window aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.reporting import CloudStatistic
from app.repositories.reporting import CloudStatisticRepository


class StatisticsService:
    """Rolls up one organization's cloud fleet counts for one window,
    idempotently."""

    def __init__(self, repo: CloudStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        resources_discovered: int,
        resources_provisioned: int,
        total_cost: float,
        budgets_exceeded: int,
        drift_detected_count: int,
        compliance_violations: int,
    ) -> CloudStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is None:
            existing = CloudStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.window_end = window_end
        existing.resources_discovered = resources_discovered
        existing.resources_provisioned = resources_provisioned
        existing.total_cost = total_cost
        existing.budgets_exceeded = budgets_exceeded
        existing.drift_detected_count = drift_detected_count
        existing.compliance_violations = compliance_violations
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
