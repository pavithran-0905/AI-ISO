"""Pure aggregation math behind mobile analytics and statistics.

Every function here takes plain numbers or already-fetched sequences,
never a repository -- the statistics service resolves raw counts, then
these functions turn them into the ratios and averages that actually
answer a question.
"""

from __future__ import annotations

from collections.abc import Sequence


def success_rate(successes: int, total: int) -> float:
    """The fraction of *total* attempts that succeeded, or ``0.0`` for
    an empty population -- an empty population has no rate to report,
    not a failing one."""
    if total <= 0:
        return 0.0
    return successes / total


def engagement_rate(engaged: int, delivered: int) -> float:
    """The fraction of delivered notifications that were engaged
    with (opened/read)."""
    return success_rate(engaged, delivered)


def crash_rate(crash_count: int, session_count: int) -> float:
    """Crashes per session."""
    return success_rate(crash_count, session_count)


def offline_usage_ratio(offline_actions: int, total_actions: int) -> float:
    """The fraction of actions performed while offline."""
    return success_rate(offline_actions, total_actions)


def average_session_duration(durations_seconds: Sequence[float]) -> float:
    """The mean session duration, or ``0.0`` for no sessions."""
    if not durations_seconds:
        return 0.0
    return sum(durations_seconds) / len(durations_seconds)


def distinct_user_count(user_ids: Sequence[str]) -> int:
    """The number of distinct users among *user_ids* -- the shape both
    DAU and MAU reduce to once the caller has already scoped the
    window."""
    return len(set(user_ids))


__all__ = [
    "average_session_duration",
    "crash_rate",
    "distinct_user_count",
    "engagement_rate",
    "offline_usage_ratio",
    "success_rate",
]
