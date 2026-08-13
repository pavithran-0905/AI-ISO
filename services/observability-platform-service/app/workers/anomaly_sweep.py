"""The anomaly detection sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Runs ``app.anomaly.engine`` over every active series' recent samples.
**Every sweep re-fetches a window wider than the nominal one**
(``anomaly_min_history_points`` buckets before the detection window, not
just the window itself), because the robust baseline needs history from
before the point under test -- fetching only the detection window would
starve the detector of exactly the context it needs to tell a spike from
a new normal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.anomaly.engine import MIN_HISTORY_POINTS
from app.services.anomaly import AnomalyDetectionService, points_from_metrics
from app.services.bundle import build_repositories
from app.types import EventPublisher

logger = get_logger("app.workers.anomaly_sweep")

_HISTORY_MULTIPLIER = 3
"""Buckets of history fetched per series, as a multiple of the engine's
own minimum. Comfortably above the floor so a series sitting exactly at
the minimum does not flicker between "evaluable" and "refused" from one
sweep to the next as individual samples roll out of the window."""


class AnomalySweepWorker:
    """Detects anomalies across every active metric series."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        lookback: timedelta = timedelta(hours=6),
        series_limit: int = 500,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._lookback = lookback
        self._series_limit = series_limit

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's active series, returning detections persisted."""
        now = datetime.now(UTC)
        window_start = now - self._lookback
        persisted = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = AnomalyDetectionService(repos.anomalies, publish=self._publish_event)

            for organization_id in await repos.metric_series.list_organization_ids():
                active_series = await repos.metric_series.list_active(
                    organization_id, since=window_start, limit=self._series_limit
                )
                for series in active_series:
                    rows = await repos.metrics.list_for_series(
                        series.id,
                        start=window_start,
                        end=now,
                        limit=max(self._series_limit, MIN_HISTORY_POINTS * _HISTORY_MULTIPLIER),
                    )
                    if len(rows) < MIN_HISTORY_POINTS:
                        continue
                    points = points_from_metrics([(row.occurred_at, row.value) for row in rows])
                    found = await service.sweep_series(
                        organization_id,
                        metric_series_id=series.id,
                        metric_name=series.name,
                        service_name=series.service_name,
                        environment=series.environment,
                        points=points,
                    )
                    persisted += len(found)
            await session.commit()

        logger.info("anomaly sweep completed", extra={"extra_fields": {"detections": persisted}})
        return persisted


__all__ = ["AnomalySweepWorker"]
