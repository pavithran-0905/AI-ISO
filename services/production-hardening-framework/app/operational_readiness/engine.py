"""Operational readiness rate computation."""

from __future__ import annotations


def readiness_rate(passed_count: int, total_count: int) -> float:
    """The fraction of operational readiness checks currently
    passing. An honest zero when nothing has been checked yet -- an
    unverified target is not "ready" by default."""
    if total_count <= 0:
        return 0.0
    return passed_count / total_count


__all__ = ["readiness_rate"]
