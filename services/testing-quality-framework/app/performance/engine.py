"""Performance threshold and regression checks."""

from __future__ import annotations


def is_within_threshold(value: float, *, threshold: float, higher_is_better: bool = False) -> bool:
    """Whether a measured *value* (latency, throughput, resource
    utilization, ...) clears its own threshold. Latency-shaped metrics
    are "lower is better" by default; throughput-shaped ones pass
    ``higher_is_better=True``."""
    if higher_is_better:
        return value >= threshold
    return value <= threshold


def is_performance_regression(
    *, baseline: float, measured: float, tolerance_percent: float
) -> bool:
    """Whether *measured* is worse than *baseline* by more than
    *tolerance_percent* -- "worse" meaning higher, since this compares
    latency-shaped (lower-is-better) metrics. A *baseline* of zero
    treats any positive *measured* value as a regression, since a
    percentage change against zero is undefined."""
    if baseline <= 0:
        return measured > 0
    percent_change = ((measured - baseline) / baseline) * 100
    return percent_change > tolerance_percent


__all__ = ["is_performance_regression", "is_within_threshold"]
