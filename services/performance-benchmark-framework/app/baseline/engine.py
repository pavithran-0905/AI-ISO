"""Baseline selection: the value a metric's own future results are
measured against."""

from __future__ import annotations

import statistics
from collections.abc import Sequence


def compute_baseline_from_samples(samples: Sequence[float]) -> float:
    """The median of a metric's own recent samples -- a single outlier
    result cannot yourself become the baseline, unlike taking the most
    recent value or a plain mean. An empty sample set yields an honest
    zero."""
    if not samples:
        return 0.0
    return statistics.median(samples)


def is_baseline_stale(
    *, baseline_value: float, recent_median: float, staleness_threshold_percent: float
) -> bool:
    """Whether a metric's own baseline has drifted far enough from its
    recent typical value that it should be recomputed, rather than
    every future result being measured against a now-outdated point."""
    if baseline_value == 0:
        return recent_median != 0
    drift_percent = abs((recent_median - baseline_value) / abs(baseline_value)) * 100.0
    return drift_percent >= staleness_threshold_percent


__all__ = ["compute_baseline_from_samples", "is_baseline_stale"]
