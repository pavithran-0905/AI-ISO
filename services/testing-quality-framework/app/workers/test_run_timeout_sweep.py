"""The test run timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every test run that has been ``RUNNING`` past its own configured
maximum age -- a test run that never reports back is not still "in
progress" forever.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import TestRunStatus
from app.pipeline.engine import is_job_stuck
from app.services.bundle import build_repositories
from app.services.test_execution import TestRunService

logger = get_logger("app.workers.test_run_timeout_sweep")


class TestRunTimeoutSweepWorker:
    """Fails test runs stuck too long in ``RUNNING``."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, max_age_hours: int
    ) -> None:
        self._session_factory = session_factory
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running test runs, returning how
        many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = TestRunService(repos.test_runs)

            for organization_id in await repos.test_runs.list_organization_ids():
                for run in await repos.test_runs.list_running(organization_id):
                    if is_job_stuck(
                        run.status,
                        started_at=run.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await service.complete(
                            run,
                            status=TestRunStatus.FAILED,
                            now=now,
                            error_message="Test run timed out.",
                        )
                        failed += 1
            await session.commit()

        logger.info("test run timeout sweep completed", extra={"extra_fields": {"failed": failed}})
        return failed


__all__ = ["TestRunTimeoutSweepWorker"]
