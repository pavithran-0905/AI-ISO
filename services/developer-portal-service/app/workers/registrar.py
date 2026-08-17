"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

SESSION_EXPIRY_SWEEP_JOB_ID = "developer-portal-session-expiry-sweep"
PLAYGROUND_SESSION_EXPIRY_SWEEP_JOB_ID = "developer-portal-playground-session-expiry-sweep"
SEARCH_INDEX_REBUILD_JOB_ID = "developer-portal-search-index-rebuild"
STATISTICS_ROLLUP_JOB_ID = "developer-portal-statistics-rollup"
PLUGIN_SUBMISSION_STALENESS_SWEEP_JOB_ID = "developer-portal-plugin-submission-staleness-sweep"


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


def register_session_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires stale developer portal sessions."""
    return _register(
        manager,
        fn,
        job_id=SESSION_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="session_expiry",
    )


def register_playground_session_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires stale code playground sessions."""
    return _register(
        manager,
        fn,
        job_id=PLAYGROUND_SESSION_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="playground_session_expiry",
    )


def register_search_index_rebuild(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rebuilds the search index from current
    published content."""
    return _register(
        manager,
        fn,
        job_id=SEARCH_INDEX_REBUILD_JOB_ID,
        interval_seconds=interval_seconds,
        component="search_index_rebuild",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up portal activity statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


def register_plugin_submission_staleness_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that auto-rejects plugin submissions stuck too
    long in validation."""
    return _register(
        manager,
        fn,
        job_id=PLUGIN_SUBMISSION_STALENESS_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="plugin_submission_staleness",
    )


__all__ = [
    "PLAYGROUND_SESSION_EXPIRY_SWEEP_JOB_ID",
    "PLUGIN_SUBMISSION_STALENESS_SWEEP_JOB_ID",
    "SEARCH_INDEX_REBUILD_JOB_ID",
    "SESSION_EXPIRY_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "register_playground_session_expiry_sweep",
    "register_plugin_submission_staleness_sweep",
    "register_search_index_rebuild",
    "register_session_expiry_sweep",
    "register_statistics_rollup",
]
