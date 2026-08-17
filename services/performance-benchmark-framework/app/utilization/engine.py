"""Resource utilization bottleneck classification."""

from __future__ import annotations

from typing import Literal

UtilizationLevel = Literal["ok", "warning", "bottleneck"]

_DEFAULT_WARNING_THRESHOLD = 75.0
_DEFAULT_BOTTLENECK_THRESHOLD = 90.0


def classify_utilization(
    utilization_percent: float,
    *,
    warning_threshold: float = _DEFAULT_WARNING_THRESHOLD,
    bottleneck_threshold: float = _DEFAULT_BOTTLENECK_THRESHOLD,
) -> UtilizationLevel:
    """Classify one utilization sample against its own warning and
    bottleneck thresholds."""
    if utilization_percent >= bottleneck_threshold:
        return "bottleneck"
    if utilization_percent >= warning_threshold:
        return "warning"
    return "ok"


def is_bottleneck(
    utilization_percent: float, *, threshold: float = _DEFAULT_BOTTLENECK_THRESHOLD
) -> bool:
    """Whether a utilization sample is at or beyond the bottleneck
    threshold."""
    return utilization_percent >= threshold


__all__ = ["UtilizationLevel", "classify_utilization", "is_bottleneck"]
