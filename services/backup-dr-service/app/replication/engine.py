"""Replication health classification.

**Lag is classified against two independent thresholds, not one.** A
single "is it lagging" boolean loses the distinction between "worth
watching" and "worth paging," which is exactly the distinction an
operator needs to decide whether to act now or at the next standup.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ReplicationStatus


class LagSeverity:
    """How concerning a replication lag reading is. Ordinal, not a
    percentage: a lag classified by a threshold crossing is an
    unambiguous fact, and a percentage-of-threshold figure invites
    averaging two readings together in a way that hides the one that
    actually crossed the line."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class LagAssessment:
    """What a lag reading means, and the status it implies."""

    severity: str
    status: ReplicationStatus
    lag_seconds: float | None
    rationale: str


def assess_lag(
    lag_seconds: float | None,
    *,
    warning_threshold_seconds: float,
    critical_threshold_seconds: float,
) -> LagAssessment:
    """Classify a replication lag reading.

    ``None`` lag (nothing has synced yet) is reported as
    :attr:`~app.models.enums.ReplicationStatus.SYNCING`, never as
    healthy or lagging -- both would be a claim about a rate that has
    not been measured yet.

    Raises:
        ValueError: When the critical threshold is not strictly above
            the warning one, which would make "critical" unreachable or
            make every warning also critical.
    """
    if critical_threshold_seconds <= warning_threshold_seconds:
        raise ValueError(
            f"critical_threshold_seconds ({critical_threshold_seconds}) must exceed "
            f"warning_threshold_seconds ({warning_threshold_seconds})."
        )
    if lag_seconds is None:
        return LagAssessment(
            severity=LagSeverity.WARNING,
            status=ReplicationStatus.SYNCING,
            lag_seconds=None,
            rationale="No successful sync has been recorded yet; lag is unmeasured.",
        )
    if lag_seconds >= critical_threshold_seconds:
        return LagAssessment(
            severity=LagSeverity.CRITICAL,
            status=ReplicationStatus.STALLED,
            lag_seconds=lag_seconds,
            rationale=(
                f"{lag_seconds:.0f}s lag exceeds the {critical_threshold_seconds:.0f}s "
                "critical threshold."
            ),
        )
    if lag_seconds >= warning_threshold_seconds:
        return LagAssessment(
            severity=LagSeverity.WARNING,
            status=ReplicationStatus.LAGGING,
            lag_seconds=lag_seconds,
            rationale=(
                f"{lag_seconds:.0f}s lag exceeds the {warning_threshold_seconds:.0f}s "
                "warning threshold."
            ),
        )
    return LagAssessment(
        severity=LagSeverity.HEALTHY,
        status=ReplicationStatus.IN_SYNC,
        lag_seconds=lag_seconds,
        rationale=(
            f"{lag_seconds:.0f}s lag is within the {warning_threshold_seconds:.0f}s threshold."
        ),
    )


@dataclass(frozen=True, slots=True)
class BandwidthAllocation:
    """How a total bandwidth budget is shared across concurrent
    replication jobs."""

    per_job_mbps: float
    job_count: int
    total_mbps: float


def allocate_bandwidth(total_mbps: float, job_count: int) -> BandwidthAllocation:
    """Split *total_mbps* evenly across *job_count* concurrent jobs.

    Raises:
        ValueError: On a non-positive total or job count. Zero jobs has
            no meaningful per-job share, and a non-positive budget could
            not replicate anything regardless of how it is split.
    """
    if total_mbps <= 0:
        raise ValueError(f"total_mbps must be positive; got {total_mbps}.")
    if job_count < 1:
        raise ValueError(f"job_count must be at least 1; got {job_count}.")
    return BandwidthAllocation(
        per_job_mbps=total_mbps / job_count, job_count=job_count, total_mbps=total_mbps
    )


__all__ = [
    "BandwidthAllocation",
    "LagAssessment",
    "LagSeverity",
    "allocate_bandwidth",
    "assess_lag",
]
