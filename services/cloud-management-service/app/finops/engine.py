"""FinOps decisions: budget threshold classification, spend
forecasting, idle-resource detection, and rightsizing recommendations.

**No utilization reading at all is never treated as "idle."** A
resource nothing has measured yet has not been proven idle -- it has
simply not been looked at, the same discipline
``app.health.engine`` applies to a device with no health readings.
"""

from __future__ import annotations


class BudgetStatus:
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


class RightsizingRecommendation:
    DOWNSIZE = "downsize"
    UPSIZE = "upsize"
    NONE = "none"


def classify_budget_status(
    current_spend: float, amount: float, *, warning_threshold: float, critical_threshold: float
) -> str:
    """Classify a budget's current standing.

    Raises:
        ValueError: On a negative *current_spend*/*amount*, or a
            non-positive *amount*.
    """
    if current_spend < 0 or amount <= 0:
        raise ValueError("current_spend must be non-negative and amount must be positive.")
    utilization = current_spend / amount
    if utilization >= 1.0:
        return BudgetStatus.EXCEEDED
    if utilization >= critical_threshold:
        return BudgetStatus.CRITICAL
    if utilization >= warning_threshold:
        return BudgetStatus.WARNING
    return BudgetStatus.OK


def forecast_period_end_spend(current_spend: float, *, elapsed_fraction: float) -> float | None:
    """Linearly extrapolate the period-end spend from *current_spend*
    and how much of the period has elapsed.

    ``None`` when *elapsed_fraction* is zero (or negative) -- there is
    no rate to extrapolate from a period that has barely started.

    Raises:
        ValueError: On a negative *current_spend*, or an
            *elapsed_fraction* outside ``[0, 1]``.
    """
    if current_spend < 0:
        raise ValueError(f"current_spend must be non-negative; got {current_spend}.")
    if not 0.0 <= elapsed_fraction <= 1.0:
        raise ValueError(f"elapsed_fraction must be within [0, 1]; got {elapsed_fraction}.")
    if elapsed_fraction == 0.0:
        return None
    return current_spend / elapsed_fraction


def is_idle_resource(utilization_fraction: float | None, *, idle_threshold_fraction: float) -> bool:
    """Whether a resource's utilization is low enough to flag as idle.

    ``None`` (nothing measured) is never idle -- an absence of evidence
    is not evidence of idleness.
    """
    if utilization_fraction is None:
        return False
    return utilization_fraction <= idle_threshold_fraction


def recommend_rightsizing(
    utilization_fraction: float | None, *, low_threshold: float, high_threshold: float
) -> str:
    """Recommend downsizing, upsizing, or leaving a resource alone,
    from its utilization.

    ``None`` (nothing measured) recommends nothing -- there is no basis
    for a sizing recommendation without a reading.
    """
    if utilization_fraction is None:
        return RightsizingRecommendation.NONE
    if utilization_fraction <= low_threshold:
        return RightsizingRecommendation.DOWNSIZE
    if utilization_fraction >= high_threshold:
        return RightsizingRecommendation.UPSIZE
    return RightsizingRecommendation.NONE


__all__ = [
    "BudgetStatus",
    "RightsizingRecommendation",
    "classify_budget_status",
    "forecast_period_end_spend",
    "is_idle_resource",
    "recommend_rightsizing",
]
