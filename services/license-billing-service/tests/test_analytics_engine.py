"""Tests for app.analytics.engine: MRR/ARR normalization and rates
with an honest denominator."""

from __future__ import annotations

import pytest

from app.analytics.engine import (
    churn_rate,
    compute_arr,
    normalize_to_monthly_recurring_revenue,
    success_rate,
)
from app.models.enums import BillingModel


class TestNormalizeToMonthlyRecurringRevenue:
    def test_monthly_is_unchanged(self) -> None:
        assert (
            normalize_to_monthly_recurring_revenue(100.0, billing_model=BillingModel.MONTHLY)
            == 100.0
        )

    def test_quarterly_divides_by_three(self) -> None:
        assert (
            normalize_to_monthly_recurring_revenue(300.0, billing_model=BillingModel.QUARTERLY)
            == 100.0
        )

    def test_annual_divides_by_twelve(self) -> None:
        assert (
            normalize_to_monthly_recurring_revenue(1200.0, billing_model=BillingModel.ANNUAL)
            == 100.0
        )

    def test_usage_based_contributes_nothing(self) -> None:
        assert (
            normalize_to_monthly_recurring_revenue(500.0, billing_model=BillingModel.USAGE_BASED)
            == 0.0
        )

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            normalize_to_monthly_recurring_revenue(-1.0, billing_model=BillingModel.MONTHLY)


class TestComputeArr:
    def test_multiplies_by_twelve(self) -> None:
        assert compute_arr(100.0) == 1200.0

    def test_zero_mrr_is_zero_arr(self) -> None:
        assert compute_arr(0.0) == 0.0

    def test_negative_mrr_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_arr(-1.0)


class TestChurnRate:
    def test_computes_fraction(self) -> None:
        assert churn_rate(5, 100) == 0.05

    def test_zero_active_at_start_is_none(self) -> None:
        assert churn_rate(0, 0) is None

    def test_negative_churned_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            churn_rate(-1, 100)

    def test_negative_active_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            churn_rate(1, -100)

    def test_churned_exceeding_active_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            churn_rate(10, 5)


class TestSuccessRate:
    def test_computes_fraction(self) -> None:
        assert success_rate(8, 2) == 0.8

    def test_no_attempts_is_none(self) -> None:
        assert success_rate(0, 0) is None

    def test_negative_succeeded_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(-1, 0)

    def test_negative_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(0, -1)
