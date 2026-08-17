"""Rate limit threshold evaluation.

Pure functions only -- the caller already resolved the current request
count for whatever window (minute/hour/day) it is checking; this
module only answers "is that count over its own limit."
"""

from __future__ import annotations


def is_rate_limited(*, current_count: int, limit: int) -> bool:
    """Whether *current_count* has reached or exceeded *limit*."""
    return current_count >= limit


def is_within_burst(*, concurrent_count: int, burst_limit: int) -> bool:
    """Whether *concurrent_count* stays within *burst_limit*."""
    return concurrent_count <= burst_limit


def remaining_capacity(*, current_count: int, limit: int) -> int:
    """How many more requests are allowed before *limit* is reached,
    never negative."""
    return max(limit - current_count, 0)


__all__ = ["is_rate_limited", "is_within_burst", "remaining_capacity"]
