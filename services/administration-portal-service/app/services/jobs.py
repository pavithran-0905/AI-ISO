"""Background job enqueueing, lifecycle transitions, and retry.

Wires ``app.jobs.engine``'s pure transition table and retry decision
onto the repositories that persist jobs and their history.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.jobs.engine import RetryDecision, TransitionResult, should_retry_job, validate_transition
from app.models.enums import JobPriority, JobStatus
from app.models.jobs import JobHistory, SystemJob
from app.repositories.jobs import JobHistoryRepository, SystemJobRepository


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class JobService:
    def __init__(self, job_repo: SystemJobRepository, history_repo: JobHistoryRepository) -> None:
        self._job_repo = job_repo
        self._history_repo = history_repo

    async def enqueue(
        self,
        organization_id: UUID,
        *,
        job_key: str,
        priority: JobPriority,
        payload: dict[str, object],
        max_attempts: int,
        now: datetime,
    ) -> SystemJob:
        job = await self._job_repo.create(
            SystemJob(
                organization_id=organization_id,
                job_key=job_key,
                priority=priority,
                payload=payload,
                max_attempts=max_attempts,
                queued_at=now,
            )
        )
        await self._record_history(job, status=JobStatus.QUEUED, now=now)
        return job

    async def transition(
        self, job: SystemJob, *, target: JobStatus, now: datetime, detail: str | None = None
    ) -> SystemJob:
        """Move *job* to *target*, raising :class:`TransitionRefusedError`
        if the transition is not allowed."""
        result = validate_transition(job.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        job.status = target
        if target == JobStatus.RUNNING and job.started_at is None:
            job.started_at = now
        if target in (
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.DEAD_LETTER,
        ):
            job.completed_at = now
        await self._job_repo.update(job)
        await self._record_history(job, status=target, now=now, detail=detail)
        return job

    async def prepare_retry(self, job: SystemJob, *, now: datetime) -> RetryDecision:
        """Whether *job* should be retried, incrementing its attempt
        count and moving it to ``RETRYING`` when it is."""
        decision = should_retry_job(
            job.status, attempt_count=job.attempt_count, max_attempts=job.max_attempts
        )
        if decision.should_retry:
            job.attempt_count += 1
            await self.transition(job, target=JobStatus.RETRYING, now=now, detail=decision.detail)
        return decision

    async def _record_history(
        self, job: SystemJob, *, status: JobStatus, now: datetime, detail: str | None = None
    ) -> JobHistory:
        return await self._history_repo.create(
            JobHistory(
                organization_id=job.organization_id,
                job_id=job.id,
                status=status,
                occurred_at=now,
                detail=detail,
            )
        )


__all__ = ["JobService", "TransitionRefusedError"]
