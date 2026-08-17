"""Upgrade analytics math: success rate, average duration, rollback
rate, and channel adoption distribution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def success_rate(succeeded: int, total: int) -> float:
    """The fraction of attempts that succeeded, or ``0.0`` if there
    were none to measure."""
    if total <= 0:
        return 0.0
    return succeeded / total


def average_duration_seconds(durations: Sequence[float]) -> float:
    """The mean of a set of durations, or ``0.0`` for an empty set."""
    if not durations:
        return 0.0
    return sum(durations) / len(durations)


def rollback_rate(rollbacks: int, upgrades: int) -> float:
    """How often an upgrade was followed by a rollback, or ``0.0`` if
    there were no upgrades to measure against."""
    if upgrades <= 0:
        return 0.0
    return rollbacks / upgrades


def channel_adoption(counts_by_channel: Mapping[str, int]) -> dict[str, float]:
    """The normalized adoption share of each release channel, summing
    to ``1.0`` across all channels (or all zero if there is no
    activity to measure)."""
    total = sum(counts_by_channel.values())
    if total <= 0:
        return dict.fromkeys(counts_by_channel, 0.0)
    return {channel: count / total for channel, count in counts_by_channel.items()}


__all__ = ["average_duration_seconds", "channel_adoption", "rollback_rate", "success_rate"]
