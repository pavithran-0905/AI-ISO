"""Statistics rollup: idempotent per-window aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.reporting import ClusterStatistic
from app.repositories.reporting import ClusterStatisticRepository


class StatisticsService:
    """Rolls up one organization's fleet counts for one window,
    idempotently."""

    def __init__(self, repo: ClusterStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        clusters_registered: int,
        clusters_healthy: int,
        clusters_degraded: int,
        clusters_unhealthy: int,
        policy_violations: int,
        compliance_violations: int,
        upgrades_completed: int,
        upgrades_failed: int,
        total_node_count: int,
    ) -> ClusterStatistic:
        existing = await self._repo.find_window(
            organization_id, window_start=window_start, window_end=window_end
        )
        if existing is None:
            existing = ClusterStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.clusters_registered = clusters_registered
        existing.clusters_healthy = clusters_healthy
        existing.clusters_degraded = clusters_degraded
        existing.clusters_unhealthy = clusters_unhealthy
        existing.policy_violations = policy_violations
        existing.compliance_violations = compliance_violations
        existing.upgrades_completed = upgrades_completed
        existing.upgrades_failed = upgrades_failed
        existing.total_node_count = total_node_count
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
