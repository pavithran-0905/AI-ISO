"""Health-gate scoring for upgrade jobs."""

from __future__ import annotations


def compute_health_score(*, passed: int, warning: int, failed: int) -> float:
    """A weighted health score in ``[0.0, 1.0]``: a ``PASSED`` check
    counts fully, a ``WARNING`` counts half, a ``FAILED`` check counts
    for nothing. An upgrade with no checks recorded yet is vacuously
    scored ``1.0`` -- nothing has failed."""
    total = passed + warning + failed
    if total <= 0:
        return 1.0
    weighted = passed + (warning * 0.5)
    return weighted / total


def is_healthy_enough(score: float, *, threshold: float) -> bool:
    """Whether a health score clears the gate needed to keep an
    upgrade running."""
    return score >= threshold


__all__ = ["compute_health_score", "is_healthy_enough"]
