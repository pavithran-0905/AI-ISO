"""Benchmark statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern every prior rollup worker in this codebase uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import BenchmarkStatistic
from app.repositories.reporting import BenchmarkStatisticRepository


class StatisticsService:
    def __init__(self, repo: BenchmarkStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        benchmark_run_count: int,
        regression_count: int,
        slo_violation_count: int,
        avg_performance_score: float,
    ) -> BenchmarkStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.benchmark_run_count = benchmark_run_count
            existing.regression_count = regression_count
            existing.slo_violation_count = slo_violation_count
            existing.avg_performance_score = avg_performance_score
            return await self._repo.update(existing)
        return await self._repo.create(
            BenchmarkStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                benchmark_run_count=benchmark_run_count,
                regression_count=regression_count,
                slo_violation_count=slo_violation_count,
                avg_performance_score=avg_performance_score,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[BenchmarkStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
