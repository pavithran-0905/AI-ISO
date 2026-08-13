"""Statistics rollup: idempotent per-window aggregation.

Counted, never averaged, exactly per
:class:`~app.models.operations.BackupStatistic`'s own docstring.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.operations import BackupStatistic
from app.repositories.operations import BackupStatisticRepository


class StatisticsService:
    """Rolls up one organization's backup/restore/replication counts for
    one window, idempotently."""

    def __init__(self, repo: BackupStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        jobs_completed: int,
        jobs_failed: int,
        bytes_backed_up: int,
        restore_jobs_completed: int,
        restore_jobs_failed: int,
        mean_restore_duration_ms: float | None,
        replication_jobs_lagging: int,
        mean_replication_lag_seconds: float | None,
        rpo_compliant_count: int,
        rpo_violated_count: int,
        rto_compliant_count: int,
        rto_violated_count: int,
    ) -> BackupStatistic:
        existing = await self._repo.find_window(
            organization_id, window_start=window_start, window_end=window_end
        )
        if existing is None:
            existing = BackupStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.jobs_completed = jobs_completed
        existing.jobs_failed = jobs_failed
        existing.bytes_backed_up = bytes_backed_up
        existing.restore_jobs_completed = restore_jobs_completed
        existing.restore_jobs_failed = restore_jobs_failed
        existing.mean_restore_duration_ms = mean_restore_duration_ms
        existing.replication_jobs_lagging = replication_jobs_lagging
        existing.mean_replication_lag_seconds = mean_replication_lag_seconds
        existing.rpo_compliant_count = rpo_compliant_count
        existing.rpo_violated_count = rpo_violated_count
        existing.rto_compliant_count = rto_compliant_count
        existing.rto_violated_count = rto_violated_count
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
