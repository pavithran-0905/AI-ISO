"""Capacity forecasting and scaling recommendations.

**A growth rate is computed only over a real elapsed period.** A
zero-or-negative period has no meaningful rate to report -- returning
``0.0`` in that case would look like "genuinely no growth" rather than
"this calculation cannot be performed."
"""

from __future__ import annotations


class ScalingRecommendation:
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NONE = "none"


def compute_growth_rate_per_day(
    previous_value: float, current_value: float, *, period_days: float
) -> float | None:
    """The average per-day change between *previous_value* and
    *current_value* over *period_days*.

    ``None`` when *period_days* is not positive -- there is no rate to
    compute over a zero-or-negative-length period.

    Raises:
        ValueError: On a negative *previous_value*/*current_value*.
    """
    if previous_value < 0 or current_value < 0:
        raise ValueError("previous_value and current_value must both be non-negative.")
    if period_days <= 0:
        return None
    return (current_value - previous_value) / period_days


def forecast_future_value(
    current_value: float, *, growth_rate_per_day: float, days_ahead: int
) -> float:
    """Linearly extrapolate a future value from *current_value* and a
    known per-day growth rate.

    Raises:
        ValueError: On a negative *current_value* or *days_ahead*.
    """
    if current_value < 0:
        raise ValueError(f"current_value must be non-negative; got {current_value}.")
    if days_ahead < 0:
        raise ValueError(f"days_ahead must be non-negative; got {days_ahead}.")
    return max(0.0, current_value + growth_rate_per_day * days_ahead)


def recommend_scaling(
    utilization_fraction: float | None, *, scale_up_threshold: float, scale_down_threshold: float
) -> str:
    """Recommend scaling up, scaling down, or leaving capacity alone,
    from a utilization reading.

    ``None`` (nothing measured) recommends nothing.
    """
    if utilization_fraction is None:
        return ScalingRecommendation.NONE
    if utilization_fraction >= scale_up_threshold:
        return ScalingRecommendation.SCALE_UP
    if utilization_fraction <= scale_down_threshold:
        return ScalingRecommendation.SCALE_DOWN
    return ScalingRecommendation.NONE


__all__ = [
    "ScalingRecommendation",
    "compute_growth_rate_per_day",
    "forecast_future_value",
    "recommend_scaling",
]
