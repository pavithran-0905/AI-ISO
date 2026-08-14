"""Cluster capacity: utilization, severity classification, and growth
rate, all with an honest denominator.

**A utilization fraction with a zero total is `None`, never `0.0` or
`1.0`.** A resource with no capacity reported yet has not been measured
at 0% or 100% used -- both are claims the data does not support.
"""

from __future__ import annotations

from dataclasses import dataclass


class CapacitySeverity:
    UNKNOWN = "unknown"
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


def compute_utilization(total: float, used: float) -> float | None:
    """The fraction of *total* consumed by *used*.

    Raises:
        ValueError: On a negative total or used amount, which cannot be
            a real capacity reading.
    """
    if total < 0 or used < 0:
        raise ValueError("total and used must both be non-negative.")
    if total == 0:
        return None
    return used / total


@dataclass(frozen=True, slots=True)
class UtilizationAssessment:
    severity: str
    utilization_fraction: float | None
    rationale: str


def classify_utilization(
    utilization_fraction: float | None, *, warning_threshold: float, critical_threshold: float
) -> UtilizationAssessment:
    """Classify a utilization reading against two independent
    thresholds.

    ``None`` (nothing measured) is ``UNKNOWN``, never assumed ``OK`` --
    a resource this service has never actually measured is not evidence
    of spare capacity.

    Raises:
        ValueError: When the critical threshold does not strictly exceed
            the warning one.
    """
    if critical_threshold <= warning_threshold:
        raise ValueError(
            f"critical_threshold ({critical_threshold}) must exceed "
            f"warning_threshold ({warning_threshold})."
        )
    if utilization_fraction is None:
        return UtilizationAssessment(
            severity=CapacitySeverity.UNKNOWN,
            utilization_fraction=None,
            rationale="No capacity reading is available.",
        )
    if utilization_fraction >= critical_threshold:
        return UtilizationAssessment(
            severity=CapacitySeverity.CRITICAL,
            utilization_fraction=utilization_fraction,
            rationale=(
                f"{utilization_fraction:.0%} utilization meets or exceeds the "
                f"{critical_threshold:.0%} critical threshold."
            ),
        )
    if utilization_fraction >= warning_threshold:
        return UtilizationAssessment(
            severity=CapacitySeverity.WARNING,
            utilization_fraction=utilization_fraction,
            rationale=(
                f"{utilization_fraction:.0%} utilization meets or exceeds the "
                f"{warning_threshold:.0%} warning threshold."
            ),
        )
    return UtilizationAssessment(
        severity=CapacitySeverity.OK,
        utilization_fraction=utilization_fraction,
        rationale=f"{utilization_fraction:.0%} utilization is within normal bounds.",
    )


def growth_rate(current: float, previous: float) -> float | None:
    """Relative change in consumption between two periods.

    ``None`` when the previous period measured zero -- dividing by zero
    would either crash or, if guarded naively, report an infinite or
    undefined growth rate that renders as garbage on a dashboard.
    """
    if previous == 0:
        return None
    return (current - previous) / previous


__all__ = [
    "CapacitySeverity",
    "UtilizationAssessment",
    "classify_utilization",
    "compute_utilization",
    "growth_rate",
]
