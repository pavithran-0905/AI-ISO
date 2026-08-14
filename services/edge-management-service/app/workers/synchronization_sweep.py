"""The synchronization sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails any synchronization execution that has been ``IN_PROGRESS`` for
longer than the configured staleness threshold -- a sync a device never
finished (dropped connection, crashed mid-transfer) must not sit
``IN_PROGRESS`` forever; nothing else in this service will ever revisit
it once the request that started it has returned.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.notifications import EdgeNotifier
from app.services.synchronization import SynchronizationService
from app.types import EventPublisher

logger = get_logger("app.workers.synchronization_sweep")


class SynchronizationSweepWorker:
    """Times out stuck synchronization executions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: EdgeNotifier,
        stale_threshold_minutes: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._stale_threshold_minutes = stale_threshold_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Fail every stuck in-progress synchronization, returning how
        many were timed out."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=self._stale_threshold_minutes)
        timed_out = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = SynchronizationService(repos.synchronization, publish=self._publish_event)

            for organization_id in await repos.synchronization.list_organization_ids():
                for sync in await repos.synchronization.list_stuck(organization_id, before=cutoff):
                    await service.fail_sync(
                        sync, error_message="Synchronization timed out without completing.", now=now
                    )
                    await self._notifier.notify_synchronization_failed(
                        device_id=str(sync.device_id),
                        sync_id=str(sync.id),
                        error_message="timed out",
                    )
                    timed_out += 1
            await session.commit()

        logger.info(
            "synchronization sweep completed", extra={"extra_fields": {"timed_out": timed_out}}
        )
        return timed_out


__all__ = ["SynchronizationSweepWorker"]
