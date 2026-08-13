"""The replication monitor worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Reclassifies every replication job's status from its currently-recorded
lag via ``app.replication.engine.assess_lag``. Measuring the lag itself
-- querying the replica's own replication position -- is target-specific
(a PostgreSQL replication slot's lag is not read the same way a Redis
replica's is) and is not wired in this build; this worker reclassifies
whatever lag was last recorded, which keeps status current even between
lag measurements.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.replication import ReplicationService

logger = get_logger("app.workers.replication_monitor")


class ReplicationMonitorWorker:
    """Reclassifies every replication job's health."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        warning_threshold_seconds: float,
        critical_threshold_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._warning_threshold = warning_threshold_seconds
        self._critical_threshold = critical_threshold_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Reclassify every job, returning how many were checked."""
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = ReplicationService(
                repos.replication_jobs,
                warning_threshold_seconds=self._warning_threshold,
                critical_threshold_seconds=self._critical_threshold,
            )

            for organization_id in await repos.replication_jobs.list_organization_ids():
                for job in await repos.replication_jobs.list_for_organization(organization_id):
                    await service.refresh_status(job)
                    checked += 1
            await session.commit()

        logger.info("replication monitor completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["ReplicationMonitorWorker"]
