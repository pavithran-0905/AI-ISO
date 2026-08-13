"""Tests for app.capacity.regression -- OLS/Theil-Sen fits and intervals."""

from __future__ import annotations

import math

import pytest

from app.capacity.enums import ConfidenceLevel, EstimatorKind, FitClass, IntervalMethod
from app.capacity.regression import (
    MIN_POINTS_FOR_QUANTILE_INTERVAL,
    influential_points,
    median_absolute_successive_difference,
    normal_quantile,
    ols_fit,
    prediction_interval,
    residual_quantile_interval,
    slope_confidence_interval,
    t_quantile,
    theil_sen_fit,
    variance_inflation_for,
)


class TestNormalQuantile:
    def test_central_region(self) -> None:
        assert normal_quantile(0.5) == pytest.approx(0.0, abs=1e-9)
        assert normal_quantile(0.975) == pytest.approx(1.959964, abs=1e-4)

    def test_outside_central_region_raises(self) -> None:
        with pytest.raises(ValueError, match="central region"):
            normal_quantile(0.001)


class TestTQuantile:
    def test_table_lookup(self) -> None:
        assert t_quantile(ConfidenceLevel.NINETY_FIVE, 10) == pytest.approx(2.228, abs=1e-3)

    def test_cornish_fisher_above_table(self) -> None:
        value = t_quantile(ConfidenceLevel.NINETY_FIVE, 1000)
        assert value == pytest.approx(1.9623, abs=0.01)

    def test_zero_degrees_of_freedom_raises(self) -> None:
        with pytest.raises(ValueError, match="degrees of freedom"):
            t_quantile(ConfidenceLevel.NINETY, 0)


class TestOlsFit:
    def test_perfect_line(self) -> None:
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 3.0, 5.0, 7.0, 9.0]
        fit = ols_fit(xs, ys)
        assert fit.slope == pytest.approx(2.0)
        assert fit.intercept == pytest.approx(1.0)
        assert fit.fit_class is FitClass.LINEAR
        assert fit.r_squared == pytest.approx(1.0, abs=1e-9)
        assert fit.estimator is EstimatorKind.OLS

    def test_constant_series(self) -> None:
        fit = ols_fit([0.0, 1.0, 2.0, 3.0], [5.0, 5.0, 5.0, 5.0])
        assert fit.fit_class is FitClass.CONSTANT
        assert fit.slope == 0.0
        assert fit.r_squared is None
        assert fit.adjusted_r_squared is None

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="differ in length"):
            ols_fit([1.0, 2.0], [1.0])

    def test_too_few_points_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot support a fit"):
            ols_fit([1.0, 2.0], [1.0, 2.0])

    def test_zero_spread_x_raises(self) -> None:
        with pytest.raises(ValueError, match="no slope to estimate"):
            ols_fit([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])

    def test_noisy_series_has_partial_fit_quality(self) -> None:
        xs = [float(i) for i in range(20)]
        ys = [2.0 * x + 1.0 + (5.0 if i % 7 == 0 else 0.0) for i, x in enumerate(xs)]
        fit = ols_fit(xs, ys)
        assert fit.residual_std > 0
        assert fit.se_slope is not None
        assert fit.t_slope is not None
        assert fit.durbin_watson is not None
        assert fit.variance_inflation >= 1.0


class TestTheilSenFit:
    def test_perfect_line(self) -> None:
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 3.0, 5.0, 7.0, 9.0]
        fit = theil_sen_fit(xs, ys)
        assert fit.slope == pytest.approx(2.0)
        assert fit.r_squared is None  # withheld by design
        assert fit.estimator is EstimatorKind.THEIL_SEN

    def test_robust_to_outlier(self) -> None:
        xs = [float(i) for i in range(10)]
        ys = [float(i) for i in range(10)]
        ys[5] = 1000.0  # one wild outlier
        fit = theil_sen_fit(xs, ys)
        assert fit.slope == pytest.approx(1.0, abs=0.5)

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="differ in length"):
            theil_sen_fit([1.0, 2.0, 3.0], [1.0, 2.0])

    def test_too_few_points_raises(self) -> None:
        with pytest.raises(ValueError):
            theil_sen_fit([1.0, 2.0], [1.0, 2.0])

    def test_too_many_buckets_raises(self) -> None:
        xs = [float(i) for i in range(401)]
        ys = [float(i) for i in range(401)]
        with pytest.raises(ValueError, match="exceeds the"):
            theil_sen_fit(xs, ys)

    def test_zero_spread_x_raises(self) -> None:
        with pytest.raises(ValueError, match="no slope to estimate"):
            theil_sen_fit([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])


class TestPredictionInterval:
    def test_width_at_least_two_t_s(self) -> None:
        xs = [float(i) for i in range(20)]
        ys = [2.0 * x + 1.0 + ((-1) ** i) for i, x in enumerate(xs)]
        fit = ols_fit(xs, ys)
        interval = prediction_interval(fit, x=fit.x_centroid, confidence=ConfidenceLevel.NINETY)
        t = t_quantile(ConfidenceLevel.NINETY, fit.degrees_of_freedom)
        assert interval.width >= 2 * t * fit.residual_std - 1e-9
        assert interval.method is IntervalMethod.STUDENT_T_PREDICTION

    def test_constant_series_interval(self) -> None:
        fit = ols_fit([0.0, 1.0, 2.0], [5.0, 5.0, 5.0])
        interval = prediction_interval(fit, x=1.0)
        assert interval.lower == pytest.approx(interval.upper)


class TestResidualQuantileInterval:
    def test_raises_below_min_points(self) -> None:
        xs = [float(i) for i in range(5)]
        ys = [float(i) for i in range(5)]
        fit = theil_sen_fit(xs, ys)
        with pytest.raises(ValueError, match="cannot support"):
            residual_quantile_interval(fit, x=1.0)

    def test_produces_band_above_min_points(self) -> None:
        xs = [float(i) for i in range(MIN_POINTS_FOR_QUANTILE_INTERVAL + 5)]
        ys = [x + ((-1) ** i) for i, x in enumerate(xs)]
        fit = theil_sen_fit(xs, ys)
        interval = residual_quantile_interval(fit, x=5.0)
        assert interval.method is IntervalMethod.RESIDUAL_QUANTILE
        assert interval.lower <= interval.upper


class TestSlopeConfidenceInterval:
    def test_none_when_no_se_slope(self) -> None:
        fit = ols_fit([0.0, 1.0, 2.0], [5.0, 5.0, 5.0])
        assert slope_confidence_interval(fit) is None

    def test_bounds_include_slope(self) -> None:
        xs = [float(i) for i in range(20)]
        ys = [2.0 * x + ((-1) ** i) for i, x in enumerate(xs)]
        fit = ols_fit(xs, ys)
        interval = slope_confidence_interval(fit)
        assert interval is not None
        assert interval.lower <= fit.slope <= interval.upper


class TestVarianceInflationFor:
    def test_none_rho_is_no_inflation(self) -> None:
        assert variance_inflation_for(None) == 1.0

    def test_low_rho_is_no_inflation(self) -> None:
        assert variance_inflation_for(0.1) == 1.0

    def test_high_rho_inflates_and_caps(self) -> None:
        assert variance_inflation_for(0.99) == pytest.approx(math.sqrt(1.9 / 0.1))


class TestInfluentialPoints:
    def test_empty_when_no_residual_spread(self) -> None:
        fit = ols_fit([0.0, 1.0, 2.0], [5.0, 5.0, 5.0])
        assert influential_points([0.0, 1.0, 2.0], fit) == ()

    def test_finds_influential_outlier(self) -> None:
        xs = [float(i) for i in range(15)]
        ys = [float(i) for i in range(15)]
        ys[0] = -500.0  # extreme leverage + residual at the edge
        fit = ols_fit(xs, ys)
        points = influential_points(xs, fit)
        assert len(points) >= 1
        assert points[0].index == 0


class TestMedianAbsoluteSuccessiveDifference:
    def test_none_below_min_points(self) -> None:
        assert median_absolute_successive_difference([1.0]) is None

    def test_computes_median_delta(self) -> None:
        result = median_absolute_successive_difference([1.0, 3.0, 2.0, 6.0])
        assert result == pytest.approx(2.0)
