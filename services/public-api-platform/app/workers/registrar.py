"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

CREDENTIAL_EXPIRY_SWEEP_JOB_ID = "public-api-platform-credential-expiry-sweep"
QUOTA_RESET_SWEEP_JOB_ID = "public-api-platform-quota-reset-sweep"
API_VERSION_LIFECYCLE_SWEEP_JOB_ID = "public-api-platform-api-version-lifecycle-sweep"
STATISTICS_ROLLUP_JOB_ID = "public-api-platform-statistics-rollup"
SANDBOX_RESET_SWEEP_JOB_ID = "public-api-platform-sandbox-reset-sweep"


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


def register_credential_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires stale credentials and warns of
    imminent expiry."""
    return _register(
        manager,
        fn,
        job_id=CREDENTIAL_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="credential_expiry",
    )


def register_quota_reset_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that resets expired quota periods and warns of
    imminent quota exhaustion."""
    return _register(
        manager,
        fn,
        job_id=QUOTA_RESET_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="quota_reset",
    )


def register_api_version_lifecycle_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that advances API versions through deprecation
    and sunset."""
    return _register(
        manager,
        fn,
        job_id=API_VERSION_LIFECYCLE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="api_version_lifecycle",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up developer platform activity
    statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


def register_sandbox_reset_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that resets stale developer sandbox sessions."""
    return _register(
        manager,
        fn,
        job_id=SANDBOX_RESET_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="sandbox_reset",
    )


__all__ = [
    "API_VERSION_LIFECYCLE_SWEEP_JOB_ID",
    "CREDENTIAL_EXPIRY_SWEEP_JOB_ID",
    "QUOTA_RESET_SWEEP_JOB_ID",
    "SANDBOX_RESET_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_api_version_lifecycle_sweep",
    "register_credential_expiry_sweep",
    "register_quota_reset_sweep",
    "register_sandbox_reset_sweep",
    "register_statistics_rollup",
]
