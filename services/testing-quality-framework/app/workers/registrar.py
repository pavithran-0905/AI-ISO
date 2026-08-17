"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

TEST_RUN_TIMEOUT_SWEEP_JOB_ID = "testing-quality-framework-test-run-timeout-sweep"
PIPELINE_TIMEOUT_SWEEP_JOB_ID = "testing-quality-framework-pipeline-timeout-sweep"
FLAKY_TEST_DETECTION_JOB_ID = "testing-quality-framework-flaky-test-detection"
COVERAGE_DROP_SWEEP_JOB_ID = "testing-quality-framework-coverage-drop-sweep"
STATISTICS_ROLLUP_JOB_ID = "testing-quality-framework-statistics-rollup"


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


def register_test_run_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails test runs stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=TEST_RUN_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="test_run_timeout",
    )


def register_pipeline_timeout_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that fails pipeline results stuck too long in
    ``RUNNING``."""
    return _register(
        manager,
        fn,
        job_id=PIPELINE_TIMEOUT_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="pipeline_timeout",
    )


def register_flaky_test_detection(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that detects newly-flaky test cases."""
    return _register(
        manager,
        fn,
        job_id=FLAKY_TEST_DETECTION_JOB_ID,
        interval_seconds=interval_seconds,
        component="flaky_test_detection",
    )


def register_coverage_drop_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that detects newly-dropped coverage."""
    return _register(
        manager,
        fn,
        job_id=COVERAGE_DROP_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="coverage_drop",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up QA activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "COVERAGE_DROP_SWEEP_JOB_ID",
    "FLAKY_TEST_DETECTION_JOB_ID",
    "PIPELINE_TIMEOUT_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "TEST_RUN_TIMEOUT_SWEEP_JOB_ID",
    "register_coverage_drop_sweep",
    "register_flaky_test_detection",
    "register_pipeline_timeout_sweep",
    "register_statistics_rollup",
    "register_test_run_timeout_sweep",
]
