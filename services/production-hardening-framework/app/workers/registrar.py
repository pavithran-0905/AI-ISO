"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

HARDENING_RUN_TIMEOUT_SWEEP_JOB_ID = "production-hardening-framework-hardening-run-timeout-sweep"
CERTIFICATE_EXPIRY_SWEEP_JOB_ID = "production-hardening-framework-certificate-expiry-sweep"
CERTIFICATION_EXPIRY_SWEEP_JOB_ID = "production-hardening-framework-certification-expiry-sweep"
PRODUCTION_READINESS_SWEEP_JOB_ID = "production-hardening-framework-production-readiness-sweep"
STATISTICS_ROLLUP_JOB_ID = "production-hardening-framework-statistics-rollup"


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


def register_hardening_run_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails hardening runs stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=HARDENING_RUN_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="hardening_run_timeout",
    )


def register_certificate_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies of certificates newly entering
    their own expiry warning window."""
    return _register(
        manager,
        fn,
        job_id=CERTIFICATE_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="certificate_expiry",
    )


def register_certification_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires overdue production
    certifications."""
    return _register(
        manager,
        fn,
        job_id=CERTIFICATION_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="certification_expiry",
    )


def register_production_readiness_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that publishes ``ProductionReady`` for
    organizations whose readiness signals now clear the threshold."""
    return _register(
        manager,
        fn,
        job_id=PRODUCTION_READINESS_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="production_readiness",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up hardening activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "CERTIFICATE_EXPIRY_SWEEP_JOB_ID",
    "CERTIFICATION_EXPIRY_SWEEP_JOB_ID",
    "HARDENING_RUN_TIMEOUT_SWEEP_JOB_ID",
    "PRODUCTION_READINESS_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_certificate_expiry_sweep",
    "register_certification_expiry_sweep",
    "register_hardening_run_timeout_sweep",
    "register_production_readiness_sweep",
    "register_statistics_rollup",
]
