"""The upgrade job timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every upgrade job that has been ``RUNNING`` past its own
configured maximum age -- an upgrade that never reports back is not
still "in progress" forever.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import UpgradeJobStatus
from app.services.bundle import build_repositories
from app.services.notifications import UpgradeNotifier
from app.services.upgrade import UpgradeJobService
from app.upgrade.engine import is_job_stuck

logger = get_logger("app.workers.upgrade_job_timeout_sweep")


class UpgradeJobTimeoutSweepWorker:
    """Fails upgrade jobs stuck too long in ``RUNNING``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: UpgradeNotifier,
        max_age_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running upgrade jobs, returning
        how many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            job_service = UpgradeJobService(repos.jobs, repos.history)

            for organization_id in await repos.jobs.list_organization_ids():
                for job in await repos.jobs.list_running(organization_id):
                    if is_job_stuck(
                        job.status,
                        started_at=job.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await job_service.complete(
                            job,
                            status=UpgradeJobStatus.FAILED,
                            now=now,
                            error_message="Upgrade job timed out.",
                        )
                        await self._notifier.notify_upgrade_failed(reason="Upgrade job timed out.")
                        failed += 1
            await session.commit()

        logger.info(
            "upgrade job timeout sweep completed", extra={"extra_fields": {"failed": failed}}
        )
        return failed


__all__ = ["UpgradeJobTimeoutSweepWorker"]
