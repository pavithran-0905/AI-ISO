"""Pure aggregation math behind developer platform analytics and
statistics."""

from __future__ import annotations

from collections.abc import Sequence


def error_rate(error_count: int, total_count: int) -> float:
    """The fraction of calls that errored, or ``0.0`` for an empty
    population -- an empty population has no rate to report, not a
    failing one."""
    if total_count <= 0:
        return 0.0
    return error_count / total_count


def average_latency_ms(latencies_ms: Sequence[float]) -> float:
    """The mean latency across *latencies_ms*, or ``0.0`` for no
    samples."""
    if not latencies_ms:
        return 0.0
    return sum(latencies_ms) / len(latencies_ms)


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


__all__ = ["average_latency_ms", "error_rate", "growth_rate"]
