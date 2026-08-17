"""Hardening statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern every prior rollup worker in this codebase uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import HardeningStatistic
from app.repositories.reporting import HardeningStatisticRepository


class StatisticsService:
    def __init__(self, repo: HardeningStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        hardening_run_count: int,
        security_finding_count: int,
        vulnerability_count: int,
        avg_hardening_score: float,
    ) -> HardeningStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.hardening_run_count = hardening_run_count
            existing.security_finding_count = security_finding_count
            existing.vulnerability_count = vulnerability_count
            existing.avg_hardening_score = avg_hardening_score
            return await self._repo.update(existing)
        return await self._repo.create(
            HardeningStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                hardening_run_count=hardening_run_count,
                security_finding_count=security_finding_count,
                vulnerability_count=vulnerability_count,
                avg_hardening_score=avg_hardening_score,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[HardeningStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
