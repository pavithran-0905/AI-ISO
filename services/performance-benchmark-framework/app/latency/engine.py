"""Latency percentile computation from raw sample sets."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencyPercentiles:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


def _percentile(sorted_samples: Sequence[float], percentile: float) -> float:
    """Nearest-rank percentile of an already-sorted sequence."""
    if not sorted_samples:
        return 0.0
    rank = max(0, min(len(sorted_samples) - 1, round(percentile / 100.0 * len(sorted_samples)) - 1))
    return sorted_samples[rank]


def compute_percentiles(samples: Sequence[float]) -> LatencyPercentiles:
    """Compute p50/p95/p99/max latency from a set of raw millisecond
    samples. An empty sample set yields all zeros -- an honest "no data
    collected yet", not a fabricated number."""
    if not samples:
        return LatencyPercentiles(p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, max_ms=0.0)
    ordered = sorted(samples)
    return LatencyPercentiles(
        p50_ms=_percentile(ordered, 50.0),
        p95_ms=_percentile(ordered, 95.0),
        p99_ms=_percentile(ordered, 99.0),
        max_ms=ordered[-1],
    )


__all__ = ["LatencyPercentiles", "compute_percentiles"]
