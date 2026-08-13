"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database (and, for
the backup scheduler, orchestration) work with no per-replica state, so
N replicas would be N times the load for an identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

BACKUP_SCHEDULER_JOB_ID = "backup-dr-backup-scheduler"
RETENTION_SWEEP_JOB_ID = "backup-dr-retention-sweep"
VERIFICATION_SWEEP_JOB_ID = "backup-dr-verification-sweep"
REPLICATION_MONITOR_JOB_ID = "backup-dr-replication-monitor"
STATISTICS_ROLLUP_JOB_ID = "backup-dr-statistics-rollup"


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


def register_backup_scheduler(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that starts every backup whose schedule is due."""
    return _register(
        manager,
        fn,
        job_id=BACKUP_SCHEDULER_JOB_ID,
        interval_seconds=interval_seconds,
        component="backup_scheduler",
    )


def register_retention_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that tiers and deletes archives past their
    retention policy."""
    return _register(
        manager,
        fn,
        job_id=RETENTION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="retention",
    )


def register_verification_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that samples and verifies backup checksums."""
    return _register(
        manager,
        fn,
        job_id=VERIFICATION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="verification",
    )


def register_replication_monitor(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that reclassifies replication lag."""
    return _register(
        manager,
        fn,
        job_id=REPLICATION_MONITOR_JOB_ID,
        interval_seconds=interval_seconds,
        component="replication",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up backup/restore/replication
    statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "BACKUP_SCHEDULER_JOB_ID",
    "REPLICATION_MONITOR_JOB_ID",
    "RETENTION_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "VERIFICATION_SWEEP_JOB_ID",
    "register_backup_scheduler",
    "register_replication_monitor",
    "register_retention_sweep",
    "register_statistics_rollup",
    "register_verification_sweep",
]
