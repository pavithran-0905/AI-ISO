"""The health sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Recomputes every cluster's overall health from its latest per-component
readings, and marks a cluster whose ``last_seen_at`` has gone stale
``OFFLINE`` -- a cluster that stopped phoning home is not still whatever
it last reported.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.health.engine import is_stale
from app.models.enums import ClusterHealthStatus
from app.services.bundle import build_repositories
from app.services.health import HealthService
from app.services.notifications import FleetNotifier
from app.types import EventPublisher

logger = get_logger("app.workers.health_sweep")


class HealthSweepWorker:
    """Recomputes overall health for every cluster and detects
    offline/stale ones."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: FleetNotifier,
        degraded_threshold: int,
        unhealthy_threshold: int,
        stale_threshold_minutes: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._degraded_threshold = degraded_threshold
        self._unhealthy_threshold = unhealthy_threshold
        self._stale_threshold_minutes = stale_threshold_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Recompute health for every cluster, returning how many were
        checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = HealthService(repos.health, repos.clusters, publish=self._publish_event)

            for organization_id in await repos.clusters.list_organization_ids():
                for cluster in await repos.clusters.list_recent(organization_id, limit=5000):
                    if is_stale(
                        cluster.last_seen_at,
                        now=now,
                        threshold_minutes=self._stale_threshold_minutes,
                    ):
                        previous_status = cluster.health_status
                        cluster.health_status = ClusterHealthStatus.OFFLINE
                        await repos.clusters.update(cluster)
                        if previous_status != ClusterHealthStatus.OFFLINE:
                            await self._notifier.notify_cluster_offline(
                                cluster_id=str(cluster.id), cluster_name=cluster.name
                            )
                    else:
                        await service.refresh_overall_status(
                            cluster,
                            degraded_threshold=self._degraded_threshold,
                            unhealthy_threshold=self._unhealthy_threshold,
                            now=now,
                        )
                    checked += 1
            await session.commit()

        logger.info("health sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["HealthSweepWorker"]
