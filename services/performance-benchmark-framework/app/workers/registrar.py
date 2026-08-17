"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

BENCHMARK_RUN_TIMEOUT_SWEEP_JOB_ID = "performance-benchmark-framework-benchmark-run-timeout-sweep"
REGRESSION_SWEEP_JOB_ID = "performance-benchmark-framework-regression-sweep"
SLO_COMPLIANCE_SWEEP_JOB_ID = "performance-benchmark-framework-slo-compliance-sweep"
CAPACITY_THRESHOLD_SWEEP_JOB_ID = "performance-benchmark-framework-capacity-threshold-sweep"
STATISTICS_ROLLUP_JOB_ID = "performance-benchmark-framework-statistics-rollup"


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


def register_benchmark_run_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails benchmark runs stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=BENCHMARK_RUN_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="benchmark_run_timeout",
    )


def register_regression_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that detects newly-regressed and newly-improved
    metrics."""
    return _register(
        manager,
        fn,
        job_id=REGRESSION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="regression",
    )


def register_slo_compliance_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that detects newly-non-compliant SLOs."""
    return _register(
        manager,
        fn,
        job_id=SLO_COMPLIANCE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="slo_compliance",
    )


def register_capacity_threshold_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that detects newly-breached capacity
    forecasts."""
    return _register(
        manager,
        fn,
        job_id=CAPACITY_THRESHOLD_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="capacity_threshold",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up benchmark activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "BENCHMARK_RUN_TIMEOUT_SWEEP_JOB_ID",
    "CAPACITY_THRESHOLD_SWEEP_JOB_ID",
    "REGRESSION_SWEEP_JOB_ID",
    "SLO_COMPLIANCE_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_benchmark_run_timeout_sweep",
    "register_capacity_threshold_sweep",
    "register_regression_sweep",
    "register_slo_compliance_sweep",
    "register_statistics_rollup",
]
