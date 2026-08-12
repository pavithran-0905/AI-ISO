"""The statistics rollup worker (docs/063 "ANALYTICS").

Rolls each organization's processing history into an hourly window.
**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**The rollup is idempotent per window**, so a tick that fails partway
through is safe to repeat: the next tick updates the rows it already wrote
rather than adding second copies that double-count every document in them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.analytics import AnalyticsService
from app.services.bundle import build_repositories

logger = get_logger("app.workers.statistics_rollup")


class StatisticsRollupWorker:
    """Recomputes every organization's processing statistics."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        window_hours: int = 1,
    ) -> None:
        self._session_factory = session_factory
        self._window_hours = window_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Roll up the last completed window, returning how many rows."""
        # The hour that has just finished, never the one in progress:
        # rolling up a partial window and rolling it up again gives two
        # different answers for the same window, and whichever ran last
        # wins.
        start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(
            hours=self._window_hours
        )
        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = AnalyticsService(repositories=repos)
            rows = await service.roll_up_all(window_start=start, window_hours=self._window_hours)
            await session.commit()

        logger.info(
            "statistics rollup completed",
            extra={"extra_fields": {"windows": len(rows), "window_start": start.isoformat()}},
        )
        return len(rows)


__all__ = ["StatisticsRollupWorker"]
