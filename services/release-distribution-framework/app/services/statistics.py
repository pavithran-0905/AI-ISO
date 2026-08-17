"""Release statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern every prior rollup worker in this codebase uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import ReleaseStatistic
from app.repositories.reporting import ReleaseStatisticRepository


class StatisticsService:
    def __init__(self, repo: ReleaseStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        release_count: int,
        promotion_count: int,
        download_count: int,
        avg_release_success_rate: float,
    ) -> ReleaseStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.release_count = release_count
            existing.promotion_count = promotion_count
            existing.download_count = download_count
            existing.avg_release_success_rate = avg_release_success_rate
            return await self._repo.update(existing)
        return await self._repo.create(
            ReleaseStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                release_count=release_count,
                promotion_count=promotion_count,
                download_count=download_count,
                avg_release_success_rate=avg_release_success_rate,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[ReleaseStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
