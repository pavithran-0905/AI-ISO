"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

BUILD_TIMEOUT_SWEEP_JOB_ID = "release-distribution-framework-build-timeout-sweep"
PROMOTION_APPROVAL_TIMEOUT_SWEEP_JOB_ID = (
    "release-distribution-framework-promotion-approval-timeout-sweep"
)
LTS_SUPPORT_EXPIRY_SWEEP_JOB_ID = "release-distribution-framework-lts-support-expiry-sweep"
EOL_SCHEDULE_SWEEP_JOB_ID = "release-distribution-framework-eol-schedule-sweep"
STATISTICS_ROLLUP_JOB_ID = "release-distribution-framework-statistics-rollup"


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


def register_build_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails release builds stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=BUILD_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="build_timeout",
    )


def register_promotion_approval_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rejects release promotions stuck too
    long in ``PENDING``."""
    return _register(
        manager,
        fn,
        job_id=PROMOTION_APPROVAL_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="promotion_approval_timeout",
    )


def register_lts_support_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies of LTS lines newly entering
    their own support-expiry warning window."""
    return _register(
        manager,
        fn,
        job_id=LTS_SUPPORT_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="lts_support_expiry",
    )


def register_eol_schedule_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies of releases newly entering
    their own end-of-life warning window."""
    return _register(
        manager,
        fn,
        job_id=EOL_SCHEDULE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="eol_schedule",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up release activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "BUILD_TIMEOUT_SWEEP_JOB_ID",
    "EOL_SCHEDULE_SWEEP_JOB_ID",
    "LTS_SUPPORT_EXPIRY_SWEEP_JOB_ID",
    "PROMOTION_APPROVAL_TIMEOUT_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_build_timeout_sweep",
    "register_eol_schedule_sweep",
    "register_lts_support_expiry_sweep",
    "register_promotion_approval_timeout_sweep",
    "register_statistics_rollup",
]
