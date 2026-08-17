"""Synthetic monitoring availability computation."""

from __future__ import annotations


def availability_percentage(*, successful_checks: int, total_checks: int) -> float:
    """The percentage of synthetic checks that succeeded, or ``100.0``
    for zero checks -- vacuously available, since nothing has failed."""
    if total_checks <= 0:
        return 100.0
    return (successful_checks / total_checks) * 100


__all__ = ["availability_percentage"]
