"""Capacity forecasting: compound growth projection and threshold
breach detection."""

from __future__ import annotations

import math


def project_value(*, current_value: float, growth_rate_percent: float, periods: float) -> float:
    """Compound-grow *current_value* at *growth_rate_percent* per period,
    for *periods* periods."""
    return current_value * float((1.0 + growth_rate_percent / 100.0) ** periods)


def is_threshold_breached(*, projected_value: float, threshold_value: float) -> bool:
    """Whether a projected value has reached or exceeded its own
    configured threshold."""
    return projected_value >= threshold_value


def periods_until_threshold(
    *, current_value: float, growth_rate_percent: float, threshold_value: float
) -> float | None:
    """How many periods of growth until *current_value* reaches
    *threshold_value*, or ``None`` if it never will at this growth
    rate (already past it counts as zero, not "never")."""
    if current_value >= threshold_value:
        return 0.0
    if growth_rate_percent <= 0 or current_value <= 0:
        return None
    ratio = threshold_value / current_value
    rate_factor = 1.0 + growth_rate_percent / 100.0
    return math.log(ratio) / math.log(rate_factor)


__all__ = ["is_threshold_breached", "periods_until_threshold", "project_value"]
