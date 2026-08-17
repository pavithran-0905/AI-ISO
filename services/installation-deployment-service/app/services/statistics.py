"""Deployment statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern every prior rollup worker in this codebase uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import DeploymentStatistic
from app.repositories.reporting import DeploymentStatisticRepository


class StatisticsService:
    def __init__(self, repo: DeploymentStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        installation_count: int,
        deployment_count: int,
        upgrade_count: int,
        rollback_count: int,
        validation_failure_count: int,
        success_count: int,
        failure_count: int,
    ) -> DeploymentStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.installation_count = installation_count
            existing.deployment_count = deployment_count
            existing.upgrade_count = upgrade_count
            existing.rollback_count = rollback_count
            existing.validation_failure_count = validation_failure_count
            existing.success_count = success_count
            existing.failure_count = failure_count
            return await self._repo.update(existing)
        return await self._repo.create(
            DeploymentStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                installation_count=installation_count,
                deployment_count=deployment_count,
                upgrade_count=upgrade_count,
                rollback_count=rollback_count,
                validation_failure_count=validation_failure_count,
                success_count=success_count,
                failure_count=failure_count,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[DeploymentStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
