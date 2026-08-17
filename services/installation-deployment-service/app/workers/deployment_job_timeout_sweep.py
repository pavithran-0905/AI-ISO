"""The deployment job timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every deployment job that has been ``RUNNING`` past its own
configured maximum age, across every job type (install, deploy,
upgrade, rollback share one lifecycle -- see ``app.deployment.engine``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.deployment.engine import is_job_stuck
from app.models.enums import DeploymentJobStatus
from app.services.bundle import build_repositories
from app.services.deployment import DeploymentJobService
from app.services.notifications import DeploymentNotifier

logger = get_logger("app.workers.deployment_job_timeout_sweep")


class DeploymentJobTimeoutSweepWorker:
    """Fails deployment jobs stuck too long in ``RUNNING``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: DeploymentNotifier,
        max_age_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running deployment jobs,
        returning how many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = DeploymentJobService(repos.jobs, repos.history, notifier=self._notifier)

            for organization_id in await repos.jobs.list_organization_ids():
                for job in await repos.jobs.list_running(organization_id):
                    if is_job_stuck(
                        job.status,
                        started_at=job.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await service.complete(
                            job,
                            status=DeploymentJobStatus.FAILED,
                            now=now,
                            error_message="Deployment job timed out.",
                        )
                        failed += 1
            await session.commit()

        logger.info(
            "deployment job timeout sweep completed", extra={"extra_fields": {"failed": failed}}
        )
        return failed


__all__ = ["DeploymentJobTimeoutSweepWorker"]
