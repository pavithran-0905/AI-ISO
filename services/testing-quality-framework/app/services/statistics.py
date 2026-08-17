"""QA statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern every prior rollup worker in this codebase uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import QaStatistic
from app.repositories.reporting import QaStatisticRepository


class StatisticsService:
    def __init__(self, repo: QaStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        test_run_count: int,
        pass_count: int,
        fail_count: int,
        flaky_count: int,
        quality_gate_failure_count: int,
        quality_score: float,
    ) -> QaStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.test_run_count = test_run_count
            existing.pass_count = pass_count
            existing.fail_count = fail_count
            existing.flaky_count = flaky_count
            existing.quality_gate_failure_count = quality_gate_failure_count
            existing.quality_score = quality_score
            return await self._repo.update(existing)
        return await self._repo.create(
            QaStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                test_run_count=test_run_count,
                pass_count=pass_count,
                fail_count=fail_count,
                flaky_count=flaky_count,
                quality_gate_failure_count=quality_gate_failure_count,
                quality_score=quality_score,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[QaStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
