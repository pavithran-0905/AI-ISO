"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

HEALTH_SWEEP_JOB_ID = "administration-portal-health-sweep"
MAINTENANCE_SWEEP_JOB_ID = "administration-portal-maintenance-sweep"
JOB_RETRY_SWEEP_JOB_ID = "administration-portal-job-retry-sweep"
API_KEY_EXPIRY_SWEEP_JOB_ID = "administration-portal-api-key-expiry-sweep"
STATISTICS_ROLLUP_JOB_ID = "administration-portal-statistics-rollup"


def _register(
    manager: SchedulerManager, fn: JobFn, *, job_id: str, interval_seconds: float, component: str
) -> Job:
    """Register one fixed-rate system job.

    Raises:
        ValueError: If *interval_seconds* is not positive.
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
    return manager.register_job(job)


def register_health_sweep(manager: SchedulerManager, fn: JobFn, *, interval_seconds: float) -> Job:
    """Register the job that checks database/cache latency for every
    organization and records health readings."""
    return _register(
        manager,
        fn,
        job_id=HEALTH_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="health",
    )


def register_maintenance_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that starts and completes maintenance windows
    on their own schedule."""
    return _register(
        manager,
        fn,
        job_id=MAINTENANCE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="maintenance",
    )


def register_job_retry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that retries failed background jobs past their
    backoff window."""
    return _register(
        manager,
        fn,
        job_id=JOB_RETRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="job_retry",
    )


def register_api_key_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires API keys past their expiry."""
    return _register(
        manager,
        fn,
        job_id=API_KEY_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="api_key_expiry",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up platform statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "API_KEY_EXPIRY_SWEEP_JOB_ID",
    "HEALTH_SWEEP_JOB_ID",
    "JOB_RETRY_SWEEP_JOB_ID",
    "MAINTENANCE_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_api_key_expiry_sweep",
    "register_health_sweep",
    "register_job_retry_sweep",
    "register_maintenance_sweep",
    "register_statistics_rollup",
]
