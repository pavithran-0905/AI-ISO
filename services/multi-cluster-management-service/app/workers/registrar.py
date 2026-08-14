"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database (and, for
the health sweep, staleness) work with no per-replica state, so N
replicas would be N times the load for an identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

HEALTH_SWEEP_JOB_ID = "multi-cluster-health-sweep"
COMPLIANCE_SWEEP_JOB_ID = "multi-cluster-compliance-sweep"
POLICY_RECONCILE_JOB_ID = "multi-cluster-policy-reconcile"
CAPACITY_ANALYSIS_JOB_ID = "multi-cluster-capacity-analysis"
STATISTICS_ROLLUP_JOB_ID = "multi-cluster-statistics-rollup"


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
    """Register the job that recomputes overall cluster health and
    detects stale (offline) clusters."""
    return _register(
        manager,
        fn,
        job_id=HEALTH_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="health",
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


def register_policy_reconcile(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that times out stuck policy propagations."""
    return _register(
        manager,
        fn,
        job_id=POLICY_RECONCILE_JOB_ID,
        interval_seconds=interval_seconds,
        component="policy",
    )


def register_capacity_analysis(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that classifies every cluster's latest capacity
    reading and warns on high utilization."""
    return _register(
        manager,
        fn,
        job_id=CAPACITY_ANALYSIS_JOB_ID,
        interval_seconds=interval_seconds,
        component="capacity",
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
    "CAPACITY_ANALYSIS_JOB_ID",
    "COMPLIANCE_SWEEP_JOB_ID",
    "HEALTH_SWEEP_JOB_ID",
    "POLICY_RECONCILE_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_capacity_analysis",
    "register_compliance_sweep",
    "register_health_sweep",
    "register_policy_reconcile",
    "register_statistics_rollup",
]
