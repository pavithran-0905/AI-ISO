"""Tests for app.capacity.engine: growth rate, forecasting, and scaling
recommendations."""

from __future__ import annotations

import pytest

from app.capacity.engine import (
    ScalingRecommendation,
    compute_growth_rate_per_day,
    forecast_future_value,
    recommend_scaling,
)


class TestComputeGrowthRatePerDay:
    def test_positive_growth(self) -> None:
        assert compute_growth_rate_per_day(10, 20, period_days=5) == 2.0

    def test_zero_period_is_none(self) -> None:
        assert compute_growth_rate_per_day(10, 20, period_days=0) is None

    def test_negative_period_is_none(self) -> None:
        assert compute_growth_rate_per_day(10, 20, period_days=-1) is None

    def test_negative_values_raise(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_growth_rate_per_day(-1, 20, period_days=5)


class TestForecastFutureValue:
    def test_extrapolates(self) -> None:
        assert forecast_future_value(10, growth_rate_per_day=2, days_ahead=5) == 20

    def test_never_goes_negative(self) -> None:
        assert forecast_future_value(10, growth_rate_per_day=-100, days_ahead=5) == 0.0

    def test_negative_current_value_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            forecast_future_value(-1, growth_rate_per_day=1, days_ahead=1)

    def test_negative_days_ahead_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            forecast_future_value(10, growth_rate_per_day=1, days_ahead=-1)


class TestRecommendScaling:
    def test_none_recommends_nothing(self) -> None:
        assert (
            recommend_scaling(None, scale_up_threshold=0.9, scale_down_threshold=0.1)
            == ScalingRecommendation.NONE
        )

    def test_high_utilization_scales_up(self) -> None:
        assert (
            recommend_scaling(0.95, scale_up_threshold=0.9, scale_down_threshold=0.1)
            == ScalingRecommendation.SCALE_UP
        )

    def test_low_utilization_scales_down(self) -> None:
        assert (
            recommend_scaling(0.05, scale_up_threshold=0.9, scale_down_threshold=0.1)
            == ScalingRecommendation.SCALE_DOWN
        )

    def test_mid_utilization_recommends_nothing(self) -> None:
        assert (
            recommend_scaling(0.5, scale_up_threshold=0.9, scale_down_threshold=0.1)
            == ScalingRecommendation.NONE
        )
