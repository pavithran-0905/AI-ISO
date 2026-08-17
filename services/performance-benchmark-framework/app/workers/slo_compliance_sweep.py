"""The SLO compliance sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies SLO Violation for any named SLO whose own latest evaluation
is non-compliant. **Edge-triggered via the latest result's own
``evaluated_at`` timestamp**, not a separate "already notified" table
-- docs/078's own DATABASE TABLES section has no such table, so,
mirroring every other edge-triggered worker in this codebase, this
worker only notifies while the SLO's own latest result still falls
within its own lookback window (twice the worker's own sweep
interval), rather than on every tick for as long as it stays
non-compliant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.domain_events import SLOViolatedEvent
from app.services.bundle import build_repositories
from app.services.notifications import BenchmarkNotifier
from app.types import EventPublisher

logger = get_logger("app.workers.slo_compliance_sweep")

_SOURCE_SERVICE = "performance-benchmark-framework"


class SloComplianceSweepWorker:
    """Notifies of newly-detected SLO non-compliance."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher,
        notifier: BenchmarkNotifier,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._notifier = notifier
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every SLO with a newly-detected violation,
        returning how many were notified."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.slo_results.list_organization_ids():
                for slo_name in await repos.slo_results.list_distinct_names(organization_id):
                    latest = await repos.slo_results.list_latest_by_name(
                        organization_id, slo_name=slo_name, limit=1
                    )
                    if not latest:
                        continue
                    result = latest[0]
                    if result.evaluated_at < lookback_cutoff:
                        continue
                    if result.is_compliant:
                        continue

                    await self._publish(
                        SLOViolatedEvent(
                            source_service=_SOURCE_SERVICE,
                            organization_id=organization_id,
                            payload={"slo_name": slo_name, "sli_type": str(result.sli_type)},
                        )
                    )
                    await self._notifier.notify_slo_violation(
                        slo_name=slo_name,
                        actual_value=result.actual_value,
                        target_value=result.target_value,
                    )
                    notified += 1

        logger.info(
            "slo compliance sweep completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["SloComplianceSweepWorker"]
