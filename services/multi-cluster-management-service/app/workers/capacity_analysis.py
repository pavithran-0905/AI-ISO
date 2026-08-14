"""The capacity analysis worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Classifies every cluster's latest reading for every resource kind and
notifies once utilization crosses the warning threshold.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.capacity.engine import CapacitySeverity, classify_utilization, compute_utilization
from app.models.enums import CapacityResourceKind
from app.services.bundle import build_repositories
from app.services.notifications import FleetNotifier

logger = get_logger("app.workers.capacity_analysis")


class CapacityAnalysisWorker:
    """Classifies every cluster's latest capacity readings and warns on
    high utilization."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: FleetNotifier,
        warning_threshold: float,
        critical_threshold: float,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Classify every cluster's latest capacity readings, returning
        how many warnings/critical readings were flagged."""
        flagged = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.clusters.list_organization_ids():
                for cluster in await repos.clusters.list_recent(organization_id, limit=5000):
                    for resource_kind in CapacityResourceKind:
                        reading = await repos.capacity.latest_for_resource(
                            cluster.id, resource_kind=resource_kind
                        )
                        if reading is None:
                            continue
                        utilization = compute_utilization(reading.total, reading.used)
                        assessment = classify_utilization(
                            utilization,
                            warning_threshold=self._warning_threshold,
                            critical_threshold=self._critical_threshold,
                        )
                        if assessment.severity in (
                            CapacitySeverity.WARNING,
                            CapacitySeverity.CRITICAL,
                        ):
                            await self._notifier.notify_capacity_warning(
                                cluster_id=str(cluster.id),
                                resource_kind=str(resource_kind),
                                utilization_fraction=assessment.utilization_fraction or 0.0,
                            )
                            flagged += 1

        logger.info("capacity analysis completed", extra={"extra_fields": {"flagged": flagged}})
        return flagged


__all__ = ["CapacityAnalysisWorker"]
