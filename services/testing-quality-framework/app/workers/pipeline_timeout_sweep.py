"""The pipeline timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every pipeline result that has been ``RUNNING`` past its own
configured maximum age.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import TestRunStatus
from app.pipeline.engine import is_job_stuck
from app.services.bundle import build_repositories
from app.services.notifications import QaNotifier
from app.services.pipeline import PipelineService

logger = get_logger("app.workers.pipeline_timeout_sweep")


class PipelineTimeoutSweepWorker:
    """Fails pipeline results stuck too long in ``RUNNING``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: QaNotifier,
        max_age_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running pipeline results,
        returning how many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = PipelineService(repos.pipeline_results, notifier=self._notifier)

            for organization_id in await repos.pipeline_results.list_organization_ids():
                for pipeline in await repos.pipeline_results.list_running(organization_id):
                    if is_job_stuck(
                        pipeline.status,
                        started_at=pipeline.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await service.complete(
                            pipeline,
                            status=TestRunStatus.FAILED,
                            now=now,
                            detail="Pipeline timed out.",
                        )
                        failed += 1
            await session.commit()

        logger.info("pipeline timeout sweep completed", extra={"extra_fields": {"failed": failed}})
        return failed


__all__ = ["PipelineTimeoutSweepWorker"]
