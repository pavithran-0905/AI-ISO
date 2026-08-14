"""Device health aggregation: component readings rolled up into one
overall verdict.

**No readings at all is `UNKNOWN`, never `HEALTHY`.** A device nothing
has checked yet has not been proven healthy -- it has simply not been
looked at.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import ComponentHealthStatus, DeviceComponent, DeviceHealthStatus


@dataclass(frozen=True, slots=True)
class ComponentReading:
    """One component's most recent health check, as the aggregation
    engine needs to see it."""

    component: DeviceComponent
    status: ComponentHealthStatus


@dataclass(frozen=True, slots=True)
class HealthAggregation:
    overall: DeviceHealthStatus
    warning_count: int
    critical_count: int
    total_count: int
    rationale: str


def aggregate_health(
    readings: Sequence[ComponentReading],
    *,
    degraded_threshold: int,
    unhealthy_threshold: int,
) -> HealthAggregation:
    """Roll every component reading up into one device-wide verdict.

    A device is ``UNHEALTHY`` once at least *unhealthy_threshold*
    components are ``CRITICAL``, ``DEGRADED`` once at least
    *degraded_threshold* components are ``WARNING`` or worse, and
    ``HEALTHY`` only when every component is ``OK``.
    """
    if not readings:
        return HealthAggregation(
            overall=DeviceHealthStatus.UNKNOWN,
            warning_count=0,
            critical_count=0,
            total_count=0,
            rationale="No component health readings are available.",
        )
    # ``==`` (StrEnum equality), never ``is``: a reading built from a row
    # freshly materialized by the ORM -- rather than found already live
    # in a session's identity map -- carries a plain ``str`` for this
    # column, not the enum instance.
    critical_count = sum(1 for r in readings if r.status == ComponentHealthStatus.CRITICAL)
    warning_count = sum(1 for r in readings if r.status == ComponentHealthStatus.WARNING)

    if critical_count >= unhealthy_threshold:
        return HealthAggregation(
            overall=DeviceHealthStatus.UNHEALTHY,
            warning_count=warning_count,
            critical_count=critical_count,
            total_count=len(readings),
            rationale=f"{critical_count} component(s) reporting critical.",
        )
    if (critical_count + warning_count) >= degraded_threshold:
        return HealthAggregation(
            overall=DeviceHealthStatus.DEGRADED,
            warning_count=warning_count,
            critical_count=critical_count,
            total_count=len(readings),
            rationale=(
                f"{warning_count} component(s) warning, {critical_count} critical, below the "
                "unhealthy threshold."
            ),
        )
    return HealthAggregation(
        overall=DeviceHealthStatus.HEALTHY,
        warning_count=warning_count,
        critical_count=critical_count,
        total_count=len(readings),
        rationale="Every component is reporting ok.",
    )


__all__ = ["ComponentReading", "HealthAggregation", "aggregate_health"]
