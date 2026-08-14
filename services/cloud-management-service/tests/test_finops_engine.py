"""Tests for app.finops.engine: budget classification, forecasting,
idle detection, and rightsizing."""

from __future__ import annotations

import pytest

from app.finops.engine import (
    BudgetStatus,
    RightsizingRecommendation,
    classify_budget_status,
    forecast_period_end_spend,
    is_idle_resource,
    recommend_rightsizing,
)


class TestClassifyBudgetStatus:
    def test_ok(self) -> None:
        assert (
            classify_budget_status(10, 100, warning_threshold=0.8, critical_threshold=0.95)
            == BudgetStatus.OK
        )

    def test_warning(self) -> None:
        assert (
            classify_budget_status(85, 100, warning_threshold=0.8, critical_threshold=0.95)
            == BudgetStatus.WARNING
        )

    def test_critical(self) -> None:
        assert (
            classify_budget_status(96, 100, warning_threshold=0.8, critical_threshold=0.95)
            == BudgetStatus.CRITICAL
        )

    def test_exceeded(self) -> None:
        assert (
            classify_budget_status(150, 100, warning_threshold=0.8, critical_threshold=0.95)
            == BudgetStatus.EXCEEDED
        )

    def test_negative_spend_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_budget_status(-1, 100, warning_threshold=0.8, critical_threshold=0.95)

    def test_non_positive_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_budget_status(0, 0, warning_threshold=0.8, critical_threshold=0.95)


class TestForecastPeriodEndSpend:
    def test_extrapolates_linearly(self) -> None:
        assert forecast_period_end_spend(50, elapsed_fraction=0.5) == 100

    def test_zero_elapsed_is_none(self) -> None:
        assert forecast_period_end_spend(50, elapsed_fraction=0.0) is None

    def test_negative_spend_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            forecast_period_end_spend(-1, elapsed_fraction=0.5)

    def test_out_of_range_elapsed_fraction_raises(self) -> None:
        with pytest.raises(ValueError, match="elapsed_fraction"):
            forecast_period_end_spend(50, elapsed_fraction=1.5)


class TestIsIdleResource:
    def test_none_is_never_idle(self) -> None:
        assert not is_idle_resource(None, idle_threshold_fraction=0.05)

    def test_low_utilization_is_idle(self) -> None:
        assert is_idle_resource(0.02, idle_threshold_fraction=0.05)

    def test_high_utilization_is_not_idle(self) -> None:
        assert not is_idle_resource(0.5, idle_threshold_fraction=0.05)


class TestRecommendRightsizing:
    def test_none_recommends_nothing(self) -> None:
        assert (
            recommend_rightsizing(None, low_threshold=0.1, high_threshold=0.9)
            == RightsizingRecommendation.NONE
        )

    def test_low_utilization_recommends_downsize(self) -> None:
        assert (
            recommend_rightsizing(0.05, low_threshold=0.1, high_threshold=0.9)
            == RightsizingRecommendation.DOWNSIZE
        )

    def test_high_utilization_recommends_upsize(self) -> None:
        assert (
            recommend_rightsizing(0.95, low_threshold=0.1, high_threshold=0.9)
            == RightsizingRecommendation.UPSIZE
        )

    def test_mid_utilization_recommends_nothing(self) -> None:
        assert (
            recommend_rightsizing(0.5, low_threshold=0.1, high_threshold=0.9)
            == RightsizingRecommendation.NONE
        )
