"""Installation/deployment analytics math: success rate, average
duration, and rollback frequency."""

from __future__ import annotations

from collections.abc import Sequence


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


def rollback_frequency(rollbacks: int, deployments: int) -> float:
    """How often a deployment was followed by a rollback, or ``0.0``
    if there were no deployments to measure against."""
    if deployments <= 0:
        return 0.0
    return rollbacks / deployments


__all__ = ["average_duration_seconds", "rollback_frequency", "success_rate"]
