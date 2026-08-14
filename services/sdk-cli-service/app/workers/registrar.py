"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

VERSION_COMPATIBILITY_SWEEP_JOB_ID = "sdk-cli-version-compatibility-sweep"
CLI_UPDATE_CHECK_SWEEP_JOB_ID = "sdk-cli-cli-update-check-sweep"
PLUGIN_UPDATE_SWEEP_JOB_ID = "sdk-cli-plugin-update-sweep"
SESSION_EXPIRY_SWEEP_JOB_ID = "sdk-cli-session-expiry-sweep"
STATISTICS_ROLLUP_JOB_ID = "sdk-cli-statistics-rollup"


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


def register_version_compatibility_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies for and disables deprecated SDK/
    CLI versions."""
    return _register(
        manager,
        fn,
        job_id=VERSION_COMPATIBILITY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="version_compatibility",
    )


def register_cli_update_check_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies for CLI versions behind the
    latest."""
    return _register(
        manager,
        fn,
        job_id=CLI_UPDATE_CHECK_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="cli_update_check",
    )


def register_plugin_update_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies for installed plugins with a
    newer available version."""
    return _register(
        manager,
        fn,
        job_id=PLUGIN_UPDATE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="plugin_update",
    )


def register_session_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that disables CLI sessions past their expiry."""
    return _register(
        manager,
        fn,
        job_id=SESSION_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="session_expiry",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up SDK/CLI activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "CLI_UPDATE_CHECK_SWEEP_JOB_ID",
    "PLUGIN_UPDATE_SWEEP_JOB_ID",
    "SESSION_EXPIRY_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "VERSION_COMPATIBILITY_SWEEP_JOB_ID",
    "register_cli_update_check_sweep",
    "register_plugin_update_sweep",
    "register_session_expiry_sweep",
    "register_statistics_rollup",
    "register_version_compatibility_sweep",
]
