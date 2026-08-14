"""Revenue analytics: MRR/ARR derivation and rates with an honest
denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
subscriptions active at the start of a window is not a 0% churn rate
(nothing churned) and not a 100% one (nothing retained either) -- it is
a window with no evidence.
"""

from __future__ import annotations

from app.models.enums import BillingModel

MONTHS_PER_YEAR = 12


def normalize_to_monthly_recurring_revenue(amount: float, *, billing_model: BillingModel) -> float:
    """Convert a subscription's periodic charge to its monthly-recurring
    equivalent.

    Usage-based/consumption/pay-as-you-go/custom billing models have no
    fixed recurring amount to normalize, so they contribute ``0.0`` to
    MRR -- their revenue is counted through actual billed usage instead,
    never estimated here.

    Raises:
        ValueError: On a negative *amount*.
    """
    if amount < 0:
        raise ValueError(f"amount must be non-negative; got {amount}.")
    model = BillingModel(billing_model)
    if model == BillingModel.MONTHLY:
        return amount
    if model == BillingModel.QUARTERLY:
        return amount / 3
    if model == BillingModel.ANNUAL:
        return amount / MONTHS_PER_YEAR
    return 0.0


def compute_arr(mrr: float) -> float:
    """Annual recurring revenue from monthly recurring revenue.

    Raises:
        ValueError: On a negative *mrr*.
    """
    if mrr < 0:
        raise ValueError(f"mrr must be non-negative; got {mrr}.")
    return mrr * MONTHS_PER_YEAR


def churn_rate(churned: int, active_at_period_start: int) -> float | None:
    """The fraction of subscriptions active at the period's start that
    churned during it.

    Raises:
        ValueError: When *churned* exceeds *active_at_period_start*, or
            either is negative.
    """
    if churned < 0 or active_at_period_start < 0:
        raise ValueError("churned and active_at_period_start must both be non-negative.")
    if churned > active_at_period_start:
        raise ValueError(
            f"churned ({churned}) cannot exceed active_at_period_start ({active_at_period_start})."
        )
    if active_at_period_start == 0:
        return None
    return churned / active_at_period_start


def success_rate(succeeded: int, failed: int) -> float | None:
    """The fraction of attempts that succeeded, or ``None`` with no
    attempts.

    Raises:
        ValueError: On a negative count.
    """
    if succeeded < 0 or failed < 0:
        raise ValueError("succeeded and failed must both be non-negative.")
    total = succeeded + failed
    if total == 0:
        return None
    return succeeded / total


__all__ = [
    "MONTHS_PER_YEAR",
    "churn_rate",
    "compute_arr",
    "normalize_to_monthly_recurring_revenue",
    "success_rate",
]
