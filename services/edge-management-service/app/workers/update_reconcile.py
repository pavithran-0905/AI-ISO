"""The update reconcile worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails any OTA update execution that has been in an in-progress status
(``PLANNED`` through ``VERIFYING``) for longer than the configured
staleness threshold, once it has actually started -- an update a device
never finished applying must not block further updates to that device
forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.operations import EdgeFirmwareRepository
from app.services.bundle import build_repositories
from app.services.notifications import EdgeNotifier
from app.services.ota import OTAService
from app.types import EventPublisher

logger = get_logger("app.workers.update_reconcile")


class UpdateReconcileWorker:
    """Times out stuck OTA update executions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: EdgeNotifier,
        max_skew: int,
        stale_threshold_minutes: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._max_skew = max_skew
        self._stale_threshold_minutes = stale_threshold_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Fail every stuck in-progress update, returning how many were
        timed out."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=self._stale_threshold_minutes)
        timed_out = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            firmware_repo: EdgeFirmwareRepository = repos.firmware
            service = OTAService(
                repos.updates, firmware_repo, publish=self._publish_event, max_skew=self._max_skew
            )

            for organization_id in await repos.updates.list_organization_ids():
                for update in await repos.updates.list_in_progress(
                    organization_id, started_before=cutoff
                ):
                    await service.fail_update(
                        update, error_message="Update timed out without completing.", now=now
                    )
                    await self._notifier.notify_ota_failed(
                        device_id=str(update.device_id), update_id=str(update.id)
                    )
                    timed_out += 1
            await session.commit()

        logger.info("update reconcile completed", extra={"extra_fields": {"timed_out": timed_out}})
        return timed_out


__all__ = ["UpdateReconcileWorker"]
