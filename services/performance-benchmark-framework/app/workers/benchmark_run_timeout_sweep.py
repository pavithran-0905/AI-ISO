"""The benchmark run timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every benchmark run that has been ``RUNNING`` past its own
configured maximum age -- a benchmark that never reports back is not
still "in progress" forever.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.benchmark.engine import is_job_stuck
from app.models.enums import BenchmarkRunStatus
from app.services.benchmark_execution import BenchmarkRunService
from app.services.bundle import build_repositories

logger = get_logger("app.workers.benchmark_run_timeout_sweep")


class BenchmarkRunTimeoutSweepWorker:
    """Fails benchmark runs stuck too long in ``RUNNING``."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, max_age_hours: int
    ) -> None:
        self._session_factory = session_factory
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running benchmark runs, returning
        how many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = BenchmarkRunService(repos.benchmark_runs)

            for organization_id in await repos.benchmark_runs.list_organization_ids():
                for run in await repos.benchmark_runs.list_running(organization_id):
                    if is_job_stuck(
                        run.status,
                        started_at=run.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await service.complete(
                            run,
                            status=BenchmarkRunStatus.FAILED,
                            now=now,
                            error_message="Benchmark run timed out.",
                        )
                        failed += 1
            await session.commit()

        logger.info(
            "benchmark run timeout sweep completed", extra={"extra_fields": {"failed": failed}}
        )
        return failed


__all__ = ["BenchmarkRunTimeoutSweepWorker"]
