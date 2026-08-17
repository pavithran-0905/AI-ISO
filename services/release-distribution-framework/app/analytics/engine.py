"""Rollup analytics: build success rate, promotion success rate, and
an equal-weighted overall release health score."""

from __future__ import annotations


def build_success_rate(succeeded_count: int, total_count: int) -> float:
    """The fraction of release builds that succeeded. An honest zero
    when nothing has run yet, not a fabricated 100%."""
    if total_count <= 0:
        return 0.0
    return succeeded_count / total_count


def promotion_success_rate(completed_count: int, total_count: int) -> float:
    """The fraction of release promotions that completed. A vacuous
    100% when nothing has been attempted yet -- there is nothing to
    have failed."""
    if total_count <= 0:
        return 1.0
    return completed_count / total_count


def release_health_score(
    *, build_success_rate_value: float, promotion_success_rate_value: float
) -> float:
    """An equal-weighted average of build and promotion success --
    the same two/three/four-way-average shape every prior AI-IOS
    analytics engine in this build uses."""
    return (build_success_rate_value + promotion_success_rate_value) / 2.0


__all__ = ["build_success_rate", "promotion_success_rate", "release_health_score"]
