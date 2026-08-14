"""Health status classification from latency and aggregation of
multiple component statuses into one overall reading.

**The overall status is always the worst of its components, never an
average.** One unhealthy dependency makes the platform unhealthy,
regardless of how many other dependencies are fine -- averaging would
let a critical outage hide behind a majority of healthy checks.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.enums import HealthCheckStatus

_SEVERITY_ORDER: dict[HealthCheckStatus, int] = {
    HealthCheckStatus.HEALTHY: 0,
    HealthCheckStatus.UNKNOWN: 1,
    HealthCheckStatus.DEGRADED: 2,
    HealthCheckStatus.UNHEALTHY: 3,
}


def classify_latency_status(
    latency_ms: float | None, *, warning_ms: float, critical_ms: float
) -> HealthCheckStatus:
    """Classify a dependency's health from its own latency reading.

    ``latency_ms is None`` (the check never completed, or was never
    run) is ``UNKNOWN`` -- absence of a reading is not evidence of
    health.

    Raises:
        ValueError: On a negative *latency_ms*, or if *critical_ms* is
            not greater than *warning_ms*.
    """
    if warning_ms >= critical_ms:
        raise ValueError(
            f"critical_ms ({critical_ms}) must be greater than warning_ms ({warning_ms})."
        )
    if latency_ms is None:
        return HealthCheckStatus.UNKNOWN
    if latency_ms < 0:
        raise ValueError(f"latency_ms must be non-negative; got {latency_ms}.")
    if latency_ms >= critical_ms:
        return HealthCheckStatus.UNHEALTHY
    if latency_ms >= warning_ms:
        return HealthCheckStatus.DEGRADED
    return HealthCheckStatus.HEALTHY


def aggregate_overall_status(statuses: Sequence[HealthCheckStatus]) -> HealthCheckStatus:
    """The worst status among every component check.

    An empty sequence (nothing has been checked yet) is ``UNKNOWN``,
    never ``HEALTHY`` -- no evidence is not the same fact as good
    evidence.
    """
    if not statuses:
        return HealthCheckStatus.UNKNOWN
    return max(statuses, key=lambda status: _SEVERITY_ORDER[HealthCheckStatus(status)])


__all__ = ["aggregate_overall_status", "classify_latency_status"]
