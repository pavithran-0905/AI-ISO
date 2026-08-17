"""Pure aggregation math behind portal analytics and statistics."""

from __future__ import annotations


def engagement_rate(engaged_count: int, total_count: int) -> float:
    """The fraction of *total_count* that engaged, or ``0.0`` for an
    empty population -- an empty population has no rate to report, not
    a failing one."""
    if total_count <= 0:
        return 0.0
    return engaged_count / total_count


def growth_rate(previous_count: int, current_count: int) -> float:
    """The fractional change from *previous_count* to *current_count*.

    A previous count of zero has no meaningful percentage growth to
    report (division by zero); this returns ``1.0`` (100%) when there
    was any growth at all from nothing, and ``0.0`` when both counts
    are zero.
    """
    if previous_count <= 0:
        return 1.0 if current_count > 0 else 0.0
    return (current_count - previous_count) / previous_count


__all__ = ["engagement_rate", "growth_rate"]
