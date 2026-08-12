"""Recurring-job registration against ``shared_core.scheduler``.

Maps this service's four background jobs onto that framework's
:class:`~shared_core.scheduler.Schedule`/:class:`~shared_core.scheduler.Job`
shapes. The polling loop, distributed locking, leader election, and retry
machinery all live in ``packages/shared-core/scheduler`` (Prompt 026).

**All four jobs are leader-elected.** Each is pure database work with no
per-replica state, so N replicas would be N times the load for an
identical result -- and two replicas running the same processing sweep
would OCR the same scan twice, which on a paid OCR backend costs real
money and on any backend doubles the wall clock for no benefit.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

PROCESSING_SWEEP_JOB_ID = "document-processing-sweep"
REVIEW_EXPIRY_SWEEP_JOB_ID = "document-review-expiry-sweep"
STATISTICS_ROLLUP_JOB_ID = "document-statistics-rollup"
RETENTION_SWEEP_JOB_ID = "document-retention-sweep"
"""Deterministic job ids, so re-registering replaces rather than leaks."""


def _register(
    manager: SchedulerManager,
    fn: JobFn,
    *,
    job_id: str,
    interval_seconds: float,
    component: str,
) -> Job:
    """Register one fixed-rate system job.

    Raises:
        ValueError: If *interval_seconds* is not positive. Zero would
            busy-loop the scheduler; negative is meaningless.
    """
    if interval_seconds <= 0:
        raise ValueError(f"The {component} interval must be positive, got {interval_seconds!r}.")
    job = Job(
        job_id=job_id,
        job_name=job_id,
        job_type=JobType.SYSTEM,
        fn=fn,
        schedule=Schedule(
            schedule_type=FrameworkScheduleType.FIXED_RATE,
            interval=timedelta(seconds=interval_seconds),
        ),
        metadata={"component": component},
    )
    # The manager's return value, not the local `job`: registration is
    # what computes the first due time, and the registry transitions a
    # copy -- so returning the object built above would hand the caller a
    # job that reads as never scheduled.
    return manager.register_job(job)


def register_processing_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that runs queued pipeline work."""
    return _register(
        manager,
        fn,
        job_id=PROCESSING_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="processing",
    )


def register_review_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that escalates overdue reviews."""
    return _register(
        manager,
        fn,
        job_id=REVIEW_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="review",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up processing statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="analytics",
    )


def register_retention_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that archives expired documents."""
    return _register(
        manager,
        fn,
        job_id=RETENTION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="retention",
    )


__all__ = [
    "PROCESSING_SWEEP_JOB_ID",
    "RETENTION_SWEEP_JOB_ID",
    "REVIEW_EXPIRY_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_processing_sweep",
    "register_retention_sweep",
    "register_review_expiry_sweep",
    "register_statistics_rollup",
]
