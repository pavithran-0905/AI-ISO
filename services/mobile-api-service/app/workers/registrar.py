"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

SESSION_EXPIRY_SWEEP_JOB_ID = "mobile-api-session-expiry-sweep"
TOKEN_EXPIRY_SWEEP_JOB_ID = "mobile-api-token-expiry-sweep"
SYNC_QUEUE_RETRY_SWEEP_JOB_ID = "mobile-api-sync-queue-retry-sweep"
PUSH_DELIVERY_RETRY_SWEEP_JOB_ID = "mobile-api-push-delivery-retry-sweep"
APP_VERSION_COMPLIANCE_SWEEP_JOB_ID = "mobile-api-app-version-compliance-sweep"


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
    """Register the job that expires stale sessions and warns of
    imminent expiry."""
    return _register(
        manager,
        fn,
        job_id=SESSION_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="session_expiry",
    )


def register_token_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires stale device-bound tokens."""
    return _register(
        manager,
        fn,
        job_id=TOKEN_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="token_expiry",
    )


def register_sync_queue_retry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that drains every organization's queued
    offline actions."""
    return _register(
        manager,
        fn,
        job_id=SYNC_QUEUE_RETRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="sync_queue_retry",
    )


def register_push_delivery_retry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that attempts delivery of pending push
    notifications."""
    return _register(
        manager,
        fn,
        job_id=PUSH_DELIVERY_RETRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="push_delivery_retry",
    )


def register_app_version_compliance_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies devices behind their platform's
    own version policy."""
    return _register(
        manager,
        fn,
        job_id=APP_VERSION_COMPLIANCE_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="app_version_compliance",
    )


__all__ = [
    "APP_VERSION_COMPLIANCE_SWEEP_JOB_ID",
    "PUSH_DELIVERY_RETRY_SWEEP_JOB_ID",
    "SESSION_EXPIRY_SWEEP_JOB_ID",
    "SYNC_QUEUE_RETRY_SWEEP_JOB_ID",
    "TOKEN_EXPIRY_SWEEP_JOB_ID",
    "register_app_version_compliance_sweep",
    "register_push_delivery_retry_sweep",
    "register_session_expiry_sweep",
    "register_sync_queue_retry_sweep",
    "register_token_expiry_sweep",
]
