"""The job retry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Retries every failed job whose exponential backoff window has elapsed,
and moves any job that has exhausted its attempt ceiling to
``DEAD_LETTER`` -- a failed job otherwise sits failed forever with
nothing deciding what happens to it next.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.jobs.engine import compute_backoff_seconds
from app.models.enums import JobStatus
from app.services.bundle import build_repositories
from app.services.jobs import JobService

logger = get_logger("app.workers.job_retry_sweep")


class JobRetrySweepWorker:
    """Retries failed jobs past their backoff window, and dead-letters
    those that have exhausted their attempts."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, backoff_base_seconds: int
    ) -> None:
        self._session_factory = session_factory
        self._backoff_base_seconds = backoff_base_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's failed jobs, returning how many
        were retried."""
        now = datetime.now(UTC)
        retried = 0
        dead_lettered = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = JobService(repos.jobs, repos.job_history)

            for organization_id in await repos.jobs.list_organization_ids():
                for job in await repos.jobs.list_by_status(
                    organization_id, status=JobStatus.FAILED
                ):
                    if job.completed_at is None:
                        continue
                    backoff = compute_backoff_seconds(
                        job.attempt_count, base_seconds=self._backoff_base_seconds
                    )
                    if now < job.completed_at + timedelta(seconds=backoff):
                        continue

                    decision = await service.prepare_retry(job, now=now)
                    if decision.should_retry:
                        retried += 1
                    else:
                        await service.transition(
                            job, target=JobStatus.DEAD_LETTER, now=now, detail=decision.detail
                        )
                        dead_lettered += 1
            await session.commit()

        logger.info(
            "job retry sweep completed",
            extra={"extra_fields": {"retried": retried, "dead_lettered": dead_lettered}},
        )
        return retried


__all__ = ["JobRetrySweepWorker"]
