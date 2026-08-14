"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

ACCOUNT_HEALTH_SWEEP_JOB_ID = "cloud-management-account-health-sweep"
DRIFT_SWEEP_JOB_ID = "cloud-management-drift-sweep"
BUDGET_SWEEP_JOB_ID = "cloud-management-budget-sweep"
COMPLIANCE_SWEEP_JOB_ID = "cloud-management-compliance-sweep"
STATISTICS_ROLLUP_JOB_ID = "cloud-management-statistics-rollup"


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


def register_account_health_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that reclassifies every account's health from
    revalidation staleness."""
    return _register(
        manager,
        fn,
        job_id=ACCOUNT_HEALTH_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="account_health",
    )


def register_drift_sweep(manager: SchedulerManager, fn: JobFn, *, interval_seconds: float) -> Job:
    """Register the job that escalates stale unresolved drift events."""
    return _register(
        manager, fn, job_id=DRIFT_SWEEP_JOB_ID, interval_seconds=interval_seconds, component="drift"
    )


def register_budget_sweep(manager: SchedulerManager, fn: JobFn, *, interval_seconds: float) -> Job:
    """Register the job that recomputes spend and threshold status for
    every budget."""
    return _register(
        manager,
        fn,
        job_id=BUDGET_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="budget",
    )


def register_compliance_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that flags overdue compliance remediations."""
    return _register(
        manager,
        fn,
        job_id=COMPLIANCE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="compliance",
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
    "ACCOUNT_HEALTH_SWEEP_JOB_ID",
    "BUDGET_SWEEP_JOB_ID",
    "COMPLIANCE_SWEEP_JOB_ID",
    "DRIFT_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_account_health_sweep",
    "register_budget_sweep",
    "register_compliance_sweep",
    "register_drift_sweep",
    "register_statistics_rollup",
]
