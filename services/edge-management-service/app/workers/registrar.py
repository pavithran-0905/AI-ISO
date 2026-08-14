"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database (and, for
the health/synchronization/update sweeps, staleness) work with no
per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

HEALTH_SWEEP_JOB_ID = "edge-management-health-sweep"
SYNCHRONIZATION_SWEEP_JOB_ID = "edge-management-synchronization-sweep"
UPDATE_RECONCILE_JOB_ID = "edge-management-update-reconcile"
PROTOCOL_SWEEP_JOB_ID = "edge-management-protocol-sweep"
STATISTICS_ROLLUP_JOB_ID = "edge-management-statistics-rollup"


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
    """Register the job that recomputes overall device health and
    detects stale (offline) devices."""
    return _register(
        manager,
        fn,
        job_id=HEALTH_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="health",
    )


def register_synchronization_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that times out stuck synchronization
    executions."""
    return _register(
        manager,
        fn,
        job_id=SYNCHRONIZATION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="synchronization",
    )


def register_update_reconcile(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that times out stuck OTA update executions."""
    return _register(
        manager,
        fn,
        job_id=UPDATE_RECONCILE_JOB_ID,
        interval_seconds=interval_seconds,
        component="update",
    )


def register_protocol_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that reclassifies every protocol endpoint's
    connectivity status."""
    return _register(
        manager,
        fn,
        job_id=PROTOCOL_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="protocol",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up fleet-wide statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "HEALTH_SWEEP_JOB_ID",
    "PROTOCOL_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "SYNCHRONIZATION_SWEEP_JOB_ID",
    "UPDATE_RECONCILE_JOB_ID",
    "register_health_sweep",
    "register_protocol_sweep",
    "register_statistics_rollup",
    "register_synchronization_sweep",
    "register_update_reconcile",
]
