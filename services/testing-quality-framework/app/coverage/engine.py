"""Coverage sufficiency and drop detection."""

from __future__ import annotations


def is_coverage_sufficient(percentage: float, *, threshold: float) -> bool:
    """Whether a coverage percentage clears its own minimum
    threshold."""
    return percentage >= threshold


def coverage_delta(*, current: float, previous: float) -> float:
    """The change in coverage percentage, positive for an improvement,
    negative for a regression."""
    return current - previous


def is_coverage_drop(*, current: float, previous: float, drop_threshold_percent: float) -> bool:
    """Whether coverage fell by more than *drop_threshold_percent*
    percentage points since the previous measurement."""
    return coverage_delta(current=current, previous=previous) <= -drop_threshold_percent


__all__ = ["coverage_delta", "is_coverage_drop", "is_coverage_sufficient"]
