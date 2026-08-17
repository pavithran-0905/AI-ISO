"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

INSTALLATION_SESSION_EXPIRY_SWEEP_JOB_ID = (
    "installation-deployment-installation-session-expiry-sweep"
)
DEPLOYMENT_JOB_TIMEOUT_SWEEP_JOB_ID = "installation-deployment-deployment-job-timeout-sweep"
CERTIFICATE_EXPIRY_SWEEP_JOB_ID = "installation-deployment-certificate-expiry-sweep"
STATISTICS_ROLLUP_JOB_ID = "installation-deployment-statistics-rollup"
UPGRADE_AVAILABILITY_SWEEP_JOB_ID = "installation-deployment-upgrade-availability-sweep"


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


def register_installation_session_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails stale installation sessions."""
    return _register(
        manager,
        fn,
        job_id=INSTALLATION_SESSION_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="installation_session_expiry",
    )


def register_deployment_job_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails deployment jobs stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=DEPLOYMENT_JOB_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="deployment_job_timeout",
    )


def register_certificate_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that recomputes certificate expiry status."""
    return _register(
        manager,
        fn,
        job_id=CERTIFICATE_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="certificate_expiry",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up installation/deployment activity
    statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


def register_upgrade_availability_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies organizations of a newly
    available platform upgrade."""
    return _register(
        manager,
        fn,
        job_id=UPGRADE_AVAILABILITY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="upgrade_availability",
    )


__all__ = [
    "CERTIFICATE_EXPIRY_SWEEP_JOB_ID",
    "DEPLOYMENT_JOB_TIMEOUT_SWEEP_JOB_ID",
    "INSTALLATION_SESSION_EXPIRY_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "UPGRADE_AVAILABILITY_SWEEP_JOB_ID",
    "register_certificate_expiry_sweep",
    "register_deployment_job_timeout_sweep",
    "register_installation_session_expiry_sweep",
    "register_statistics_rollup",
    "register_upgrade_availability_sweep",
]
