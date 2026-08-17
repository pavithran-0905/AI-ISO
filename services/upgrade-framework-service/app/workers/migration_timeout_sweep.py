"""The migration timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every migration step that has been ``RUNNING`` past its own
configured maximum age.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import UpgradeJobStatus
from app.services.bundle import build_repositories
from app.services.migrations import MigrationService
from app.services.notifications import UpgradeNotifier
from app.upgrade.engine import is_job_stuck

logger = get_logger("app.workers.migration_timeout_sweep")


class MigrationTimeoutSweepWorker:
    """Fails migration steps stuck too long in ``RUNNING``."""

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
        """Sweep every organization's running migrations, returning how
        many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = MigrationService(repos.migration_history, notifier=self._notifier)

            for organization_id in await repos.migration_history.list_organization_ids():
                for migration in await repos.migration_history.list_running(organization_id):
                    if is_job_stuck(
                        migration.status,
                        started_at=migration.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await service.complete(migration, status=UpgradeJobStatus.FAILED, now=now)
                        failed += 1
            await session.commit()

        logger.info("migration timeout sweep completed", extra={"extra_fields": {"failed": failed}})
        return failed


__all__ = ["MigrationTimeoutSweepWorker"]
