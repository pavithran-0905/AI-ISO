"""Benchmark comparison and regression detection."""

from __future__ import annotations


def percent_change(*, baseline: float, measured: float) -> float:
    """The percentage change from *baseline* to *measured*, positive
    for an increase. A *baseline* of zero returns ``0.0`` for a
    matching zero *measured* value and ``100.0`` for any positive one,
    since a percentage change against a zero baseline is otherwise
    undefined."""
    if baseline == 0:
        return 0.0 if measured == 0 else 100.0
    return ((measured - baseline) / baseline) * 100


def is_benchmark_regression(
    *, baseline: float, measured: float, tolerance_percent: float, higher_is_better: bool = True
) -> bool:
    """Whether a benchmark's *measured* value regressed against its
    own *baseline* by more than *tolerance_percent*. For a
    "higher is better" benchmark (throughput), a regression is a drop;
    for a "lower is better" one (duration), a regression is a rise."""
    change = percent_change(baseline=baseline, measured=measured)
    if higher_is_better:
        return change < -tolerance_percent
    return change > tolerance_percent


__all__ = ["is_benchmark_regression", "percent_change"]
