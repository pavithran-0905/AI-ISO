"""The coverage drop sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies Coverage Dropped when a coverage type's own latest
measurement fell by more than its own configured threshold against
the one before it. **Edge-triggered via the latest report's own
``created_at`` timestamp**, the same lookback-window shape every other
edge-triggered worker in this codebase uses, so a coverage type stuck
below its previous peak does not re-notify on every tick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.coverage.engine import is_coverage_drop
from app.models.enums import CoverageType
from app.services.bundle import build_repositories
from app.services.notifications import QaNotifier

logger = get_logger("app.workers.coverage_drop_sweep")

_REQUIRED_REPORTS_FOR_COMPARISON = 2


class CoverageDropSweepWorker:
    """Notifies of a newly-detected coverage drop, per coverage type."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: QaNotifier,
        drop_threshold_percent: float,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._drop_threshold_percent = drop_threshold_percent
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every coverage type with a newly-detected drop,
        returning how many were notified."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.coverage_reports.list_organization_ids():
                for coverage_type in await repos.coverage_reports.list_distinct_types(
                    organization_id
                ):
                    latest_two = await repos.coverage_reports.list_latest_by_type(
                        organization_id,
                        coverage_type=coverage_type,
                        limit=_REQUIRED_REPORTS_FOR_COMPARISON,
                    )
                    if len(latest_two) < _REQUIRED_REPORTS_FOR_COMPARISON:
                        continue
                    current, previous = latest_two[0], latest_two[1]

                    if current.created_at < lookback_cutoff:
                        continue
                    if not is_coverage_drop(
                        current=current.percentage,
                        previous=previous.percentage,
                        drop_threshold_percent=self._drop_threshold_percent,
                    ):
                        continue

                    await self._notifier.notify_coverage_dropped(
                        coverage_type=CoverageType(coverage_type).value,
                        current=current.percentage,
                        previous=previous.percentage,
                    )
                    notified += 1

        logger.info("coverage drop sweep completed", extra={"extra_fields": {"notified": notified}})
        return notified


__all__ = ["CoverageDropSweepWorker"]
