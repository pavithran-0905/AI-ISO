"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**The rollup is idempotent per window.** A tick that fails partway
through is safe to repeat: the next tick recomputes and overwrites the
same window's row rather than adding a second copy that double-counts
everything in it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from shared_core.database.base import BaseModel
from shared_core.logging.logger import get_logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import LogLevel, SpanStatus
from app.models.operations import ObservabilityStatistic
from app.models.signals import LogEntry, Metric, ObservabilityEvent, TraceSpan
from app.services.bundle import build_repositories

logger = get_logger("app.workers.statistics_rollup")


async def _count(
    session: AsyncSession,
    model: type[BaseModel],
    organization_id: UUID,
    column: Any,
    *,
    start: datetime,
    end: datetime,
    extra: Sequence[Any] = (),
) -> int:
    stmt = (
        select(func.count())
        .select_from(model)
        .where(model.organization_id == organization_id, column >= start, column < end, *extra)
    )
    return (await session.execute(stmt)).scalar_one()


class StatisticsRollupWorker:
    """Recomputes every organization's observability statistics."""

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
        """Roll up the last completed window, returning how many windows."""
        # The hour that has just finished, never the one in progress: rolling
        # up a partial window and then rolling it up again gives two
        # different answers for the same window, and whichever ran last wins.
        window_end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=self._window_hours)
        rolled = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.metric_series.list_organization_ids():
                metrics_ingested = await _count(
                    session,
                    Metric,
                    organization_id,
                    Metric.occurred_at,
                    start=window_start,
                    end=window_end,
                )
                logs_ingested = await _count(
                    session,
                    LogEntry,
                    organization_id,
                    LogEntry.occurred_at,
                    start=window_start,
                    end=window_end,
                )
                error_logs = await _count(
                    session,
                    LogEntry,
                    organization_id,
                    LogEntry.occurred_at,
                    start=window_start,
                    end=window_end,
                    extra=(LogEntry.level == LogLevel.ERROR,),
                )
                spans_ingested = await _count(
                    session,
                    TraceSpan,
                    organization_id,
                    TraceSpan.started_at,
                    start=window_start,
                    end=window_end,
                )
                error_spans = await _count(
                    session,
                    TraceSpan,
                    organization_id,
                    TraceSpan.started_at,
                    start=window_start,
                    end=window_end,
                    extra=(TraceSpan.status == SpanStatus.ERROR,),
                )
                events_ingested = await _count(
                    session,
                    ObservabilityEvent,
                    organization_id,
                    ObservabilityEvent.occurred_at,
                    start=window_start,
                    end=window_end,
                )

                existing = await repos.statistics.find_window(
                    organization_id, window_start=window_start, window_end=window_end
                )
                if existing is None:
                    existing = ObservabilityStatistic(
                        organization_id=organization_id,
                        window_start=window_start,
                        window_end=window_end,
                    )
                    session.add(existing)

                existing.metrics_ingested = metrics_ingested
                existing.logs_ingested = logs_ingested
                existing.spans_ingested = spans_ingested
                existing.events_ingested = events_ingested
                existing.error_log_count = error_logs
                existing.error_span_count = error_spans
                await session.flush()
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed",
            extra={
                "extra_fields": {"organizations": rolled, "window_start": window_start.isoformat()}
            },
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
