"""Recurring-job registration against ``shared_core.scheduler``.

**All five jobs are leader-elected.** Each is pure database work with
no per-replica state, so N replicas would be N times the load for an
identical result.
"""

from __future__ import annotations

from datetime import timedelta

from shared_core.scheduler import Job, JobFn, JobType, Schedule, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType

SUBSCRIPTION_RENEWAL_SWEEP_JOB_ID = "license-billing-subscription-renewal-sweep"
LICENSE_EXPIRY_SWEEP_JOB_ID = "license-billing-license-expiry-sweep"
QUOTA_RESET_SWEEP_JOB_ID = "license-billing-quota-reset-sweep"
INVOICE_GENERATION_SWEEP_JOB_ID = "license-billing-invoice-generation-sweep"
STATISTICS_ROLLUP_JOB_ID = "license-billing-statistics-rollup"


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


def register_subscription_renewal_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that notifies for upcoming renewals/trial
    expiry and expires subscriptions past their grace period."""
    return _register(
        manager,
        fn,
        job_id=SUBSCRIPTION_RENEWAL_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="subscription_renewal",
    )


def register_license_expiry_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that expires licenses past their expiry."""
    return _register(
        manager,
        fn,
        job_id=LICENSE_EXPIRY_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="license_expiry",
    )


def register_quota_reset_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that opens the current period's usage window
    for every quota."""
    return _register(
        manager,
        fn,
        job_id=QUOTA_RESET_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="quota_reset",
    )


def register_invoice_generation_sweep(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that issues one invoice per billing period and
    marks overdue invoices as such."""
    return _register(
        manager,
        fn,
        job_id=INVOICE_GENERATION_SWEEP_JOB_ID,
        interval_seconds=interval_seconds,
        component="invoice_generation",
    )


def register_statistics_rollup(
    manager: SchedulerManager, fn: JobFn, *, interval_seconds: float
) -> Job:
    """Register the job that rolls up revenue and billing statistics."""
    return _register(
        manager,
        fn,
        job_id=STATISTICS_ROLLUP_JOB_ID,
        interval_seconds=interval_seconds,
        component="statistics",
    )


__all__ = [
    "INVOICE_GENERATION_SWEEP_JOB_ID",
    "LICENSE_EXPIRY_SWEEP_JOB_ID",
    "QUOTA_RESET_SWEEP_JOB_ID",
    "STATISTICS_ROLLUP_JOB_ID",
    "SUBSCRIPTION_RENEWAL_SWEEP_JOB_ID",
    "register_invoice_generation_sweep",
    "register_license_expiry_sweep",
    "register_quota_reset_sweep",
    "register_statistics_rollup",
    "register_subscription_renewal_sweep",
]
