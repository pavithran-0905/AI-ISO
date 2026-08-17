"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

UPGRADE_JOB_TIMEOUT_SWEEP_JOB_ID = "upgrade-framework-upgrade-job-timeout-sweep"
MIGRATION_TIMEOUT_SWEEP_JOB_ID = "upgrade-framework-migration-timeout-sweep"
RELEASE_ADOPTION_SWEEP_JOB_ID = "upgrade-framework-release-adoption-sweep"
HEALTH_GATE_ENFORCEMENT_JOB_ID = "upgrade-framework-health-gate-enforcement"
STATISTICS_ROLLUP_JOB_ID = "upgrade-framework-statistics-rollup"


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


def register_upgrade_job_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails upgrade jobs stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=UPGRADE_JOB_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="upgrade_job_timeout",
    )


def register_migration_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails migration steps stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=MIGRATION_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="migration_timeout",
    )


def register_release_adoption_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies of newly available release
    versions."""
    return _register(
        manager,
        fn,
        job_id=RELEASE_ADOPTION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="release_adoption",
    )


def register_health_gate_enforcement(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that auto-pauses running upgrade jobs with a
    failed health-gate check."""
    return _register(
        manager,
        fn,
        job_id=HEALTH_GATE_ENFORCEMENT_JOB_ID,
        interval_seconds=interval_seconds,
        component="health_gate_enforcement",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up upgrade/rollback/migration
    activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "HEALTH_GATE_ENFORCEMENT_JOB_ID",
    "MIGRATION_TIMEOUT_SWEEP_JOB_ID",
    "RELEASE_ADOPTION_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "UPGRADE_JOB_TIMEOUT_SWEEP_JOB_ID",
    "register_health_gate_enforcement",
    "register_migration_timeout_sweep",
    "register_release_adoption_sweep",
    "register_statistics_rollup",
    "register_upgrade_job_timeout_sweep",
]
