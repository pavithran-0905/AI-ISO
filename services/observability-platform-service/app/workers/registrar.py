"""Recurring-job registration against ``shared_core.scheduler``.

Maps this service's five background jobs onto that framework's
``Schedule``/``Job`` shapes. The polling loop, distributed locking,
leader election, and retry machinery all live in
``packages/shared-core/scheduler`` (Prompt 026).

**All five jobs are leader-elected.** Each is pure database work with no
per-replica state, so N replicas would be N times the load for an
identical result -- and two replicas running the same anomaly sweep
would persist the same detection twice were it not for
:meth:`AnomalyDetectionRepository.find_existing`'s guard, which is a
second line of defence, not a substitute for not doing the redundant
work at all.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

SLO_EVALUATION_JOB_ID = "observability-slo-evaluation"
ANOMALY_SWEEP_JOB_ID = "observability-anomaly-sweep"
TOPOLOGY_REBUILD_JOB_ID = "observability-topology-rebuild"
RETENTION_SWEEP_JOB_ID = "observability-retention-sweep"
STATISTICS_ROLLUP_JOB_ID = "observability-statistics-rollup"
"""Deterministic job ids, so re-registering replaces rather than leaks."""


def _register(
    manager: SchedulerManager, fn: JobFn, *, job_id: str, interval_seconds: float, component: str
) -> Job:
    """Register one fixed-rate system job.

    Raises:
        ValueError: If *interval_seconds* is not positive. Zero would
            busy-loop the scheduler; negative is meaningless.
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
    # The manager's return value, not the local `job`: registration is what
    # computes the first due time, and the registry transitions a copy -- so
    # returning the object built above would hand the caller a job that
    # reads as never scheduled.
    return manager.register_job(job)


def register_slo_evaluation(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that evaluates every enabled SLO."""
    return _register(
        manager,
        fn,
        job_id=SLO_EVALUATION_JOB_ID,
        interval_seconds=interval_seconds,
        component="slo",
    )


def register_anomaly_sweep(manager: SchedulerManager, fn: JobFn, *, interval_seconds: float) -> Job:
    """Register the job that scans metric series for anomalies."""
    return _register(
        manager,
        fn,
        job_id=ANOMALY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="anomaly",
    )


def register_topology_rebuild(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rebuilds the service dependency graph."""
    return _register(
        manager,
        fn,
        job_id=TOPOLOGY_REBUILD_JOB_ID,
        interval_seconds=interval_seconds,
        component="topology",
    )


def register_retention_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that applies retention policy."""
    return _register(
        manager,
        fn,
        job_id=RETENTION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="retention",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up observability statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "ANOMALY_SWEEP_JOB_ID",
    "RETENTION_SWEEP_JOB_ID",
    "SLO_EVALUATION_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "TOPOLOGY_REBUILD_JOB_ID",
    "register_anomaly_sweep",
    "register_retention_sweep",
    "register_slo_evaluation",
    "register_statistics_rollup",
    "register_topology_rebuild",
]
