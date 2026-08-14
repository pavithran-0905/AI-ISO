"""Cluster health aggregation: component readings rolled up into one
overall verdict, and staleness detection for clusters that stopped
reporting.

**No readings at all is `UNKNOWN`, never `HEALTHY`.** A cluster nothing
has checked yet has not been proven healthy -- it has simply not been
looked at, and defaulting an absence of evidence to "healthy" is exactly
the failure mode that lets a genuinely down cluster sit unnoticed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import ClusterComponent, ClusterHealthStatus, ComponentHealthStatus


@dataclass(frozen=True, slots=True)
class ComponentReading:
    """One component's most recent health check, as the aggregation
    engine needs to see it."""

    component: ClusterComponent
    status: ComponentHealthStatus


@dataclass(frozen=True, slots=True)
class HealthAggregation:
    overall: ClusterHealthStatus
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
    """Roll every component reading up into one cluster-wide verdict.

    A cluster is ``UNHEALTHY`` once at least *unhealthy_threshold*
    components are ``CRITICAL``, ``DEGRADED`` once at least
    *degraded_threshold* components are ``WARNING`` or worse, and
    ``HEALTHY`` only when every component is ``OK``. Any ``UNKNOWN``
    component reading counts toward neither threshold -- an unread
    component is not evidence of a problem, but it also cannot be
    counted as passing.
    """
    if not readings:
        return HealthAggregation(
            overall=ClusterHealthStatus.UNKNOWN,
            warning_count=0,
            critical_count=0,
            total_count=0,
            rationale="No component health readings are available.",
        )
    # ``==`` (StrEnum equality), never ``is``: a reading built from a row
    # freshly materialized by the ORM -- rather than found already live in
    # a session's identity map -- carries a plain ``str`` for this column,
    # not the enum instance, since the column is declared as plain
    # ``String`` with no Enum type decorator.
    critical_count = sum(1 for r in readings if r.status == ComponentHealthStatus.CRITICAL)
    warning_count = sum(1 for r in readings if r.status == ComponentHealthStatus.WARNING)

    if critical_count >= unhealthy_threshold:
        return HealthAggregation(
            overall=ClusterHealthStatus.UNHEALTHY,
            warning_count=warning_count,
            critical_count=critical_count,
            total_count=len(readings),
            rationale=f"{critical_count} component(s) reporting critical.",
        )
    if (critical_count + warning_count) >= degraded_threshold:
        return HealthAggregation(
            overall=ClusterHealthStatus.DEGRADED,
            warning_count=warning_count,
            critical_count=critical_count,
            total_count=len(readings),
            rationale=(
                f"{warning_count} component(s) warning, {critical_count} critical, below the "
                "unhealthy threshold."
            ),
        )
    return HealthAggregation(
        overall=ClusterHealthStatus.HEALTHY,
        warning_count=warning_count,
        critical_count=critical_count,
        total_count=len(readings),
        rationale="Every component is reporting ok.",
    )


def is_stale(last_seen_at: datetime | None, *, now: datetime, threshold_minutes: int) -> bool:
    """Whether a cluster has gone quiet long enough to be treated as
    offline.

    ``last_seen_at is None`` (never reported at all) is stale by
    definition -- there is no evidence of it ever having been reachable.
    """
    if last_seen_at is None:
        return True
    return now - last_seen_at > timedelta(minutes=threshold_minutes)


__all__ = ["ComponentReading", "HealthAggregation", "aggregate_health", "is_stale"]
