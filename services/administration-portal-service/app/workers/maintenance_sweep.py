"""The maintenance sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Starts every approved maintenance window whose start time has arrived,
and completes every in-progress window whose end time has passed --
autonomous rolling maintenance execution rather than a human watching a
clock.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.maintenance.engine import is_due_to_complete, is_due_to_start
from app.models.enums import MaintenanceStatus
from app.services.bundle import build_repositories
from app.services.maintenance import MaintenanceService
from app.types import EventPublisher

logger = get_logger("app.workers.maintenance_sweep")


class MaintenanceSweepWorker:
    """Starts and completes maintenance windows on their own schedule."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, publish_event: EventPublisher
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's maintenance windows, returning
        how many were transitioned."""
        now = datetime.now(UTC)
        transitioned = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = MaintenanceService(repos.maintenance_windows, publish=self._publish_event)

            for organization_id in await repos.maintenance_windows.list_organization_ids():
                for window in await repos.maintenance_windows.list_by_status(
                    organization_id, status=MaintenanceStatus.APPROVED
                ):
                    if is_due_to_start(window.status, starts_at=window.starts_at, now=now):
                        await service.transition(window, target=MaintenanceStatus.IN_PROGRESS)
                        transitioned += 1

                for window in await repos.maintenance_windows.list_by_status(
                    organization_id, status=MaintenanceStatus.IN_PROGRESS
                ):
                    if is_due_to_complete(window.status, ends_at=window.ends_at, now=now):
                        await service.transition(window, target=MaintenanceStatus.COMPLETED)
                        transitioned += 1
            await session.commit()

        logger.info(
            "maintenance sweep completed", extra={"extra_fields": {"transitioned": transitioned}}
        )
        return transitioned


__all__ = ["MaintenanceSweepWorker"]
