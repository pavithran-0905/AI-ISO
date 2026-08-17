"""The flaky test detection worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies Flaky Test Detected for any test case whose own recent
results mix ``PASSED`` and ``FAILED`` outcomes. **Edge-triggered via
the most recent result's own ``created_at`` timestamp**, not a
separate "already notified" table -- docs/077's own DATABASE TABLES
section has no such table, so, mirroring every other edge-triggered
worker in this codebase, this worker only notifies while the case's
own latest result still falls within its own lookback window (twice
the worker's own sweep interval), rather than on every tick for as
long as the case stays flaky.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.engine import is_flaky
from app.models.enums import TestResultStatus
from app.services.bundle import build_repositories
from app.services.notifications import QaNotifier

logger = get_logger("app.workers.flaky_test_detection")

_RECENT_RESULTS_PER_CASE = 5


class FlakyTestDetectionWorker:
    """Notifies of newly-detected flaky test cases."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: QaNotifier,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Detect newly-flaky test cases across every organization,
        returning how many were notified."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.test_results.list_organization_ids():
                for test_case_id in await repos.test_results.list_distinct_case_ids(
                    organization_id
                ):
                    recent_results = await repos.test_results.list_recent_for_case(
                        organization_id, test_case_id=test_case_id, limit=_RECENT_RESULTS_PER_CASE
                    )
                    if not recent_results:
                        continue
                    latest = recent_results[0]
                    if latest.created_at < lookback_cutoff:
                        continue

                    statuses = [TestResultStatus(row.status) for row in recent_results]
                    if not is_flaky(statuses):
                        continue

                    test_case = await repos.test_cases.require_by_id(test_case_id)
                    await self._notifier.notify_flaky_test_detected(test_case_name=test_case.name)
                    notified += 1

        logger.info(
            "flaky test detection completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["FlakyTestDetectionWorker"]
