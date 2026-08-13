"""The backup scheduler worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Starts a backup job for every schedule whose ``next_run_at`` has
arrived, then advances that schedule to its next due time -- the two
happen in the same tick so a schedule can never fire twice for the same
due time even if the worker is briefly slow between them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backup.engine import compute_next_run
from app.services.backup import BackupJobService
from app.services.bundle import build_repositories
from app.types import EventPublisher

logger = get_logger("app.workers.backup_scheduler")


class BackupSchedulerWorker:
    """Starts every backup whose schedule is due."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, publish_event: EventPublisher
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Start every due schedule's job, returning how many were started."""
        now = datetime.now(UTC)
        started = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            job_service = BackupJobService(repos.jobs, publish=self._publish_event)

            for organization_id in await repos.targets.list_organization_ids():
                for schedule in await repos.schedules.list_due(organization_id, now=now):
                    target = await repos.targets.require_in_org(organization_id, schedule.target_id)
                    await job_service.start_job(
                        organization_id,
                        target=target,
                        backup_type=schedule.backup_type,
                        schedule_id=schedule.id,
                        parent_job_id=None,
                        now=now,
                    )
                    schedule.last_run_at = now
                    if schedule.frequency != "custom_cron":
                        schedule.next_run_at = compute_next_run(
                            schedule.frequency, last_run_at=now, now=now
                        )
                    await repos.schedules.update(schedule)
                    started += 1
            await session.commit()

        logger.info(
            "backup scheduler sweep completed", extra={"extra_fields": {"started": started}}
        )
        return started


__all__ = ["BackupSchedulerWorker"]
