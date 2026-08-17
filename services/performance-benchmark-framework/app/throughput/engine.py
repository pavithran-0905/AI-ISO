"""Throughput rate computation and drop detection."""

from __future__ import annotations


def compute_requests_per_second(*, request_count: int, duration_seconds: float) -> float:
    """Requests per second over a window. A non-positive duration
    yields an honest zero rather than dividing by zero."""
    if duration_seconds <= 0:
        return 0.0
    return request_count / duration_seconds


def is_throughput_drop(*, current: float, previous: float, drop_threshold_percent: float) -> bool:
    """Whether throughput fell by at least *drop_threshold_percent*
    against its own previous measurement."""
    if previous <= 0:
        return False
    drop_percent = ((previous - current) / previous) * 100.0
    return drop_percent >= drop_threshold_percent


__all__ = ["compute_requests_per_second", "is_throughput_drop"]
