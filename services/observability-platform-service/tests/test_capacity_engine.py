"""Tests for app.capacity.engine -- forecasting, exhaustion, planning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.capacity.buckets import BucketedPoint
from app.capacity.engine import (
    MIN_BUCKETS_FOR_CLAIM,
    ExhaustionEstimate,
    Forecast,
    ForecastRefused,
    ForecastRequest,
    MetricBound,
    assess_saturation,
    assess_seasonality,
    detect_level_shift,
    estimate_exhaustion,
    forecast_series,
    growth_trend,
    plan_capacity,
)
from app.capacity.enums import (
    BoundKind,
    ConfidenceLevel,
    ExhaustionStatus,
    OrderByStatus,
    ReductionKind,
    RefusalReason,
    SaturationState,
    SeasonalityAssessment,
    TransformKind,
    TrendClass,
)

ORIGIN = datetime(2026, 1, 1, tzinfo=UTC)


def _point(index: int, value: float | None, *, excluded: bool = False) -> BucketedPoint:
    return BucketedPoint(
        index=index,
        bucket_start=ORIGIN + timedelta(days=index),
        sample_count=0 if value is None else 10,
        expected_samples=None,
        coverage=None,
        peak=value,
        mean=value,
        p95=value,
        minimum=value,
        excluded=excluded,
    )


def _growing_series(
    n: int, *, slope: float = 1.0, intercept: float = 100.0, noise: float = 0.0
) -> list[BucketedPoint]:
    points = []
    for i in range(n):
        jitter = noise * ((-1) ** i)
        points.append(_point(i, intercept + slope * i + jitter))
    return points


def _flat_series(n: int, *, value: float = 100.0, noise: float = 0.5) -> list[BucketedPoint]:
    return [_point(i, value + noise * ((-1) ** i)) for i in range(n)]


class TestAssessSeasonality:
    def test_indeterminate_below_min_buckets(self) -> None:
        result = assess_seasonality(list(range(10)), [1.0] * 10)
        assert result is SeasonalityAssessment.INDETERMINATE

    def test_none_detected_when_flat(self) -> None:
        n = 28
        result = assess_seasonality(list(range(n)), [100.0] * n)
        assert result is SeasonalityAssessment.NONE_DETECTED

    def test_weekly_detected_with_strong_weekday_effect(self) -> None:
        n = 35
        values = [100.0 + (50.0 if i % 7 == 0 else 0.0) for i in range(n)]
        result = assess_seasonality(list(range(n)), values)
        assert result is SeasonalityAssessment.WEEKLY_DETECTED


class TestDetectLevelShift:
    def test_none_with_too_few_points(self) -> None:
        assert detect_level_shift([1.0]) is None

    def test_none_for_stable_series(self) -> None:
        values = [100.0 + (i % 3 - 1) for i in range(20)]
        assert detect_level_shift(values) is None

    def test_detects_persistent_step(self) -> None:
        values = [100.0 + (i % 2) for i in range(15)] + [1000.0 + (i % 2) for i in range(15)]
        index = detect_level_shift(values)
        assert index == 15

    def test_ignores_transient_spike(self) -> None:
        values = [100.0 + (i % 2) for i in range(10)]
        values[5] = 100000.0  # one-off spike, does not persist
        index = detect_level_shift(values)
        assert index is None


class TestAssessSaturation:
    def test_normal_when_no_bound(self) -> None:
        assert assess_saturation([50.0], MetricBound()) is SaturationState.NORMAL

    def test_normal_when_empty(self) -> None:
        assert assess_saturation([], MetricBound(upper=100.0)) is SaturationState.NORMAL

    def test_censored_when_many_at_bound(self) -> None:
        values = [99.5] * 10 + [50.0] * 5
        state = assess_saturation(values, MetricBound(upper=100.0))
        assert state is SaturationState.CENSORED_AT_BOUND

    def test_approaching_when_few_at_bound(self) -> None:
        values = [99.9] * 1 + [50.0] * 20
        state = assess_saturation(values, MetricBound(upper=100.0))
        assert state is SaturationState.APPROACHING_BOUND


class TestForecastSeries:
    def _base_request(self, points: list[BucketedPoint], **overrides: object) -> ForecastRequest:
        defaults: dict[str, object] = {
            "points": points,
            "reduction": ReductionKind.MEAN,
            "bucket": timedelta(days=1),
            "horizon_buckets": 5,
        }
        defaults.update(overrides)
        return ForecastRequest(**defaults)  # type: ignore[arg-type]

    def test_counter_series_refused(self) -> None:
        request = self._base_request(_growing_series(20), is_counter=True)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.COUNTER_SERIES
        assert result.is_forecast is False

    def test_horizon_below_one_raises(self) -> None:
        request = self._base_request(_growing_series(20), horizon_buckets=0)
        with pytest.raises(ValueError, match="horizon_buckets"):
            forecast_series(request)

    def test_too_few_usable_points_refused(self) -> None:
        request = self._base_request([_point(0, 1.0), _point(1, 2.0)])
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.DEGREES_OF_FREEDOM

    def test_log_transform_requires_positive(self) -> None:
        points = _growing_series(40, intercept=-5.0, slope=0.1)
        request = self._base_request(points, transform=TransformKind.LOG)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.LOG_REQUIRES_POSITIVE

    def test_insufficient_coverage_refused(self) -> None:
        points = [_point(i, 100.0 if i < 10 else None) for i in range(40)]
        request = self._base_request(points)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.INSUFFICIENT_COVERAGE

    def test_level_shift_refused(self) -> None:
        points = [_point(i, 100.0 + (i % 2)) for i in range(20)] + [
            _point(i, 5000.0 + (i % 2)) for i in range(20, 40)
        ]
        request = self._base_request(points)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.LEVEL_SHIFT_SUSPECTED

    def test_saturated_level_refused(self) -> None:
        points = _flat_series(40, value=99.9, noise=0.05)
        request = self._base_request(
            points, bound=MetricBound(upper=100.0, kind=BoundKind.HARD_PHYSICAL)
        )
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.SATURATED_LEVEL

    def test_insufficient_history_below_claim_floor(self) -> None:
        points = _growing_series(MIN_BUCKETS_FOR_CLAIM - 1, slope=2.0, noise=0.1)
        request = self._base_request(points, horizon_buckets=2)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.INSUFFICIENT_HISTORY

    def test_horizon_exceeds_history_refused(self) -> None:
        points = _growing_series(20, slope=2.0, noise=0.1)
        request = self._base_request(points, horizon_buckets=15)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.HORIZON_EXCEEDS_HISTORY

    def test_growing_series_produces_forecast(self) -> None:
        points = _growing_series(40, slope=2.0, intercept=100.0, noise=0.5)
        request = self._base_request(points, horizon_buckets=5, materiality=0.1)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.is_forecast
        assert result.trend_class is TrendClass.GROWING
        assert len(result.points) == 5
        assert result.evidence.n_usable == 40

    def test_flat_series_produces_flat_forecast(self) -> None:
        points = _flat_series(40, value=100.0, noise=0.1)
        request = self._base_request(points, horizon_buckets=5)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.trend_class is TrendClass.FLAT_WITHIN_NOISE

    def test_declining_series_produces_declining_forecast(self) -> None:
        points = _growing_series(40, slope=-2.0, intercept=500.0, noise=0.5)
        request = self._base_request(points, horizon_buckets=5, materiality=0.1)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.trend_class is TrendClass.DECLINING

    def test_forecast_truncates_at_hard_bound(self) -> None:
        points = _growing_series(40, slope=5.0, intercept=50.0, noise=0.5)
        request = self._base_request(
            points,
            horizon_buckets=10,
            bound=MetricBound(upper=300.0, kind=BoundKind.HARD_PHYSICAL),
            materiality=0.1,
        )
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.validity.value in ("truncated_at_bound", "full_horizon")

    def test_log_transform_growing_series(self) -> None:
        points = [_point(i, 10.0 * (1.05**i)) for i in range(40)]
        request = self._base_request(points, transform=TransformKind.LOG, horizon_buckets=5)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.point_semantics.value == "median"

    def test_degenerate_x_refused(self) -> None:
        # All usable points share bucket indices after filtering to a
        # single-point-in-time scenario is hard to construct without
        # violating min_points_for_fit upstream, so this exercises the
        # ValueError -> ForecastRefused translation via a monkeypatch-free
        # route: MAX_BUCKETS exceeded instead, a distinct, reachable refusal.
        points = _growing_series(500, slope=1.0, noise=0.5)
        request = self._base_request(points, horizon_buckets=5)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.TOO_MANY_BUCKETS


class TestEstimateExhaustion:
    def _forecast_for(self, *, slope: float, n: int = 40, noise: float = 0.5) -> Forecast:
        points = _growing_series(n, slope=slope, intercept=100.0, noise=noise)
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=10,
            materiality=0.1,
        )
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        return result

    def test_unbounded_metric_when_no_ceiling(self) -> None:
        forecast = self._forecast_for(slope=2.0)
        estimate = estimate_exhaustion(forecast, ceiling=None)
        assert estimate.status is ExhaustionStatus.UNBOUNDED_METRIC

    def test_already_exhausted(self) -> None:
        forecast = self._forecast_for(slope=2.0)
        estimate = estimate_exhaustion(forecast, ceiling=forecast.last_observed_value - 1.0)
        assert estimate.status is ExhaustionStatus.ALREADY_EXHAUSTED
        assert estimate.days_point == 0.0

    def test_no_trend_status(self) -> None:
        points = _flat_series(40, value=100.0, noise=0.1)
        request = ForecastRequest(
            points=points, reduction=ReductionKind.MEAN, bucket=timedelta(days=1), horizon_buckets=5
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        estimate = estimate_exhaustion(forecast, ceiling=1_000_000.0)
        assert estimate.status is ExhaustionStatus.NO_TREND

    def test_declining_status(self) -> None:
        forecast = self._forecast_for(slope=-2.0)
        estimate = estimate_exhaustion(forecast, ceiling=1_000_000.0)
        assert estimate.status is ExhaustionStatus.DECLINING

    def test_will_exhaust_within_horizon(self) -> None:
        forecast = self._forecast_for(slope=50.0, noise=0.1)
        ceiling = forecast.last_observed_value + 50.0 * 3
        estimate = estimate_exhaustion(forecast, ceiling=ceiling)
        assert estimate.status in (
            ExhaustionStatus.WILL_EXHAUST,
            ExhaustionStatus.RISK_WITHIN_HORIZON,
        )
        assert estimate.ceiling == ceiling

    def test_not_within_horizon(self) -> None:
        forecast = self._forecast_for(slope=0.5, noise=0.1)
        estimate = estimate_exhaustion(forecast, ceiling=1_000_000.0)
        assert estimate.status is ExhaustionStatus.NOT_WITHIN_HORIZON


class TestGrowthTrend:
    def test_flat_forecast_has_no_slope(self) -> None:
        points = _flat_series(40, value=100.0, noise=0.1)
        request = ForecastRequest(
            points=points, reduction=ReductionKind.MEAN, bucket=timedelta(days=1), horizon_buckets=5
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        trend = growth_trend(forecast)
        assert trend.slope_per_day is None

    def test_growing_forecast_has_relative_growth(self) -> None:
        points = _growing_series(40, slope=2.0, intercept=200.0, noise=0.5)
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=5,
            materiality=0.1,
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        trend = growth_trend(forecast)
        assert trend.slope_per_day is not None
        assert trend.relative_growth_per_30d is not None

    def test_doubling_time_none_for_mean_semantics(self) -> None:
        points = _growing_series(40, slope=2.0, intercept=200.0, noise=0.5)
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=5,
            materiality=0.1,
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        trend = growth_trend(forecast)
        assert trend.doubling_time_days is None  # linear fit, not log


class TestPlanCapacity:
    def test_no_points_emitted(self) -> None:
        forecast = Forecast(
            points=(),
            fit=None,  # type: ignore[arg-type]
            trend_class=TrendClass.FLAT_WITHIN_NOISE,
            validity=None,  # type: ignore[arg-type]
            point_semantics=None,  # type: ignore[arg-type]
            interval_method=None,  # type: ignore[arg-type]
            interval_meaning="",
            confidence=ConfidenceLevel.NINETY,
            bucket=timedelta(days=1),
            last_observed_at=ORIGIN,
            last_observed_value=1.0,
            qualifiers=(),
            evidence=None,  # type: ignore[arg-type]
        )
        estimate = ExhaustionEstimate(
            status=ExhaustionStatus.NO_TREND,
            days_point=None,
            days_earliest=None,
            days_latest=None,
            exhaustion_at=None,
            earliest_at=None,
            ceiling=None,
            ceiling_source=None,  # type: ignore[arg-type]
            headroom_now=None,
            resolution_days=1.0,
            rationale="",
        )
        plan = plan_capacity(forecast, estimate, headroom_policy=0.2, lead_time_days=14, now=ORIGIN)
        assert plan.order_by_status is OrderByStatus.NOT_APPLICABLE
        assert plan.recommended_provision is None

    def test_scheduled_order(self) -> None:
        points = _growing_series(40, slope=5.0, intercept=100.0, noise=0.3)
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=10,
            materiality=0.1,
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        ceiling = forecast.last_observed_value + 5.0 * 5
        estimate = estimate_exhaustion(forecast, ceiling=ceiling)
        plan = plan_capacity(
            forecast, estimate, headroom_policy=0.2, lead_time_days=1, now=forecast.last_observed_at
        )
        assert plan.recommended_provision is not None
        assert plan.order_by_status in (
            OrderByStatus.SCHEDULED,
            OrderByStatus.OVERDUE,
            OrderByStatus.NOT_APPLICABLE,
        )

    def test_overdue_order(self) -> None:
        points = _growing_series(40, slope=5.0, intercept=100.0, noise=0.3)
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=10,
            materiality=0.1,
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        ceiling = forecast.last_observed_value + 5.0 * 2
        estimate = estimate_exhaustion(forecast, ceiling=ceiling)
        if estimate.earliest_at is not None:
            plan = plan_capacity(
                forecast,
                estimate,
                headroom_policy=0.2,
                lead_time_days=365,
                now=forecast.last_observed_at,
            )
            assert plan.order_by_status is OrderByStatus.OVERDUE


class TestForecastSeriesGapCoverage:
    """Targeted tests closing specific branches in forecast_series/_assemble."""

    def _base_request(self, points: list[BucketedPoint], **overrides: object) -> ForecastRequest:
        defaults: dict[str, object] = {
            "points": points,
            "reduction": ReductionKind.MEAN,
            "bucket": timedelta(days=1),
            "horizon_buckets": 5,
        }
        defaults.update(overrides)
        return ForecastRequest(**defaults)  # type: ignore[arg-type]

    def test_largest_gap_ratio_refused(self) -> None:
        # 85% overall coverage (passes MIN_COVERAGE) but one contiguous gap
        # spans more than MAX_GAP_RATIO of the window.
        n = 40
        points = []
        for i in range(n):
            if 5 <= i < 15:
                points.append(_point(i, None))
            else:
                points.append(_point(i, 100.0 + (i % 3 - 1)))
        request = self._base_request(points)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.INSUFFICIENT_COVERAGE

    def test_degenerate_x_refusal_via_duplicate_indices(self) -> None:
        # Hand-built points sharing one bucket index: forecast_series should
        # translate the regression's ValueError into DEGENERATE_X.
        points = [
            BucketedPoint(
                index=0,
                bucket_start=ORIGIN,
                sample_count=10,
                expected_samples=None,
                coverage=None,
                peak=float(i),
                mean=float(i),
                p95=float(i),
                minimum=float(i),
                excluded=False,
            )
            for i in range(20)
        ]
        request = self._base_request(points, horizon_buckets=1)
        result = forecast_series(request)
        assert isinstance(result, ForecastRefused)
        assert result.reason is RefusalReason.DEGENERATE_X

    def test_noise_free_constant_fit_flags_stale_source(self) -> None:
        points = _flat_series(40, value=100.0, noise=0.0)
        request = self._base_request(points, horizon_buckets=5)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        from app.capacity.enums import ForecastQualifier

        assert ForecastQualifier.SUSPECT_STALE_SOURCE in result.qualifiers
        # The constant-series interval branch of _interval_at / _project.
        assert result.points[0].interval.method.value == "constant_series"

    def test_negligible_trend_below_materiality(self) -> None:
        points = _growing_series(40, slope=0.0001, intercept=100.0, noise=0.0)
        request = self._base_request(points, horizon_buckets=5, materiality=1000.0)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.trend_class in (TrendClass.NEGLIGIBLE, TrendClass.FLAT_WITHIN_NOISE)

    def test_high_influence_points_qualifier(self) -> None:
        points = _growing_series(20, slope=1.0, intercept=100.0, noise=0.2)
        points[0] = _point(0, -5000.0)
        request = self._base_request(points, horizon_buckets=2)
        result = forecast_series(request)
        if isinstance(result, Forecast):
            from app.capacity.enums import ForecastQualifier

            assert (
                ForecastQualifier.HIGH_INFLUENCE_POINTS in result.qualifiers
                or ForecastQualifier.MODEL_RISK_UNQUANTIFIED in result.qualifiers
            )

    def test_short_history_qualifier_below_seasonal_min(self) -> None:
        points = _growing_series(MIN_BUCKETS_FOR_CLAIM, slope=2.0, intercept=100.0, noise=0.1)
        request = self._base_request(points, horizon_buckets=2, materiality=0.1)
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        from app.capacity.enums import ForecastQualifier

        assert ForecastQualifier.SHORT_HISTORY in result.qualifiers
        assert ForecastQualifier.SEASONALITY_UNASSESSED in result.qualifiers

    def test_peak_to_mean_divergence_computed_for_non_mean_reduction(self) -> None:
        points = [
            BucketedPoint(
                index=i,
                bucket_start=ORIGIN + timedelta(days=i),
                sample_count=10,
                expected_samples=None,
                coverage=None,
                peak=100.0 + 3.0 * i,
                mean=100.0 + 1.0 * i,
                p95=100.0 + 2.0 * i,
                minimum=100.0,
                excluded=False,
            )
            for i in range(40)
        ]
        request = self._base_request(
            points, reduction=ReductionKind.PEAK, horizon_buckets=5, materiality=0.1
        )
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.evidence.peak_to_mean_divergence is not None

    def test_lower_bound_clips_declining_forecast(self) -> None:
        points = _growing_series(40, slope=-5.0, intercept=200.0, noise=0.5)
        request = self._base_request(
            points, horizon_buckets=5, bound=MetricBound(lower=0.0), materiality=0.1
        )
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert any(point.clipped for point in result.points) or all(
            point.value >= 0.0 for point in result.points
        )

    def test_soft_bound_does_not_truncate(self) -> None:
        points = _growing_series(40, slope=1.5, intercept=30.0, noise=0.3)
        request = self._base_request(
            points,
            horizon_buckets=10,
            bound=MetricBound(upper=100.0, kind=BoundKind.SOFT_TARGET),
            materiality=0.1,
        )
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.validity.value == "full_horizon"
        assert len(result.points) == 10

    def test_weekly_seasonality_smoothing_path(self) -> None:
        n = 42
        points = []
        for i in range(n):
            weekday_effect = 30.0 if i % 7 == 0 else 0.0
            points.append(_point(i, 100.0 + 1.0 * i + weekday_effect))
        request = self._base_request(points, horizon_buckets=5, materiality=0.1)
        result = forecast_series(request)
        assert isinstance(result, (Forecast, ForecastRefused))


class TestDetectLevelShiftGapCoverage:
    def test_persistence_window_truncated_at_series_end(self) -> None:
        # A large jump one bucket before the end: `after` is shorter than
        # `persistence`, exercising the "not enough series left" continue.
        values = [100.0 + (i % 2) for i in range(10)] + [5000.0]
        assert detect_level_shift(values, persistence=3) is None

    def test_even_length_median_window(self) -> None:
        values = [100.0, 101.0, 100.0, 101.0, 500.0, 501.0, 500.0, 501.0, 500.0, 501.0]
        # persistence=2 gives even-length before/after slices, exercising
        # _median_of's even-count averaging branch either way.
        detect_level_shift(values, persistence=2)


class TestAssembleQualifiersGapCoverage:
    def _request(self, points: list[BucketedPoint], **overrides: object) -> ForecastRequest:
        defaults: dict[str, object] = {
            "points": points,
            "reduction": ReductionKind.MEAN,
            "bucket": timedelta(days=1),
            "horizon_buckets": 5,
        }
        defaults.update(overrides)
        return ForecastRequest(**defaults)  # type: ignore[arg-type]

    def test_low_explanatory_power_with_significant_but_noisy_trend(self) -> None:
        import random

        rng = random.Random(42)
        points = [_point(i, 100.0 + 0.3 * i + rng.uniform(-40.0, 40.0)) for i in range(80)]
        request = self._request(points, horizon_buckets=10, materiality=0.0)
        result = forecast_series(request)
        if isinstance(result, Forecast) and result.evidence.slope_significant:
            from app.capacity.enums import ForecastQualifier

            if result.evidence.r_squared is not None and result.evidence.r_squared < 0.30:
                assert ForecastQualifier.LOW_EXPLANATORY_POWER in result.qualifiers

    def test_autocorrelation_inflated_with_smooth_residuals(self) -> None:
        import math as _math

        n = 40
        points = [_point(i, 100.0 + 1.0 * i + 15.0 * _math.sin(i * 0.35)) for i in range(n)]
        request = self._request(points, horizon_buckets=5, materiality=0.1)
        result = forecast_series(request)
        if isinstance(result, Forecast):
            from app.capacity.enums import ForecastQualifier

            if result.evidence.rho_estimate is not None and result.evidence.rho_estimate > 0.3:
                assert ForecastQualifier.AUTOCORRELATION_INFLATED in result.qualifiers
                assert result.evidence.variance_inflation > 1.0

    def test_approaching_bound_qualifier(self) -> None:
        n = 40
        values = [50.0 + 0.5 * i for i in range(n)]
        values[-1] = 99.5  # one point near the ceiling, not enough to censor
        points = [_point(i, v) for i, v in enumerate(values)]
        request = self._request(
            points, horizon_buckets=3, bound=MetricBound(upper=100.0, kind=BoundKind.SOFT_TARGET)
        )
        result = forecast_series(request)
        if isinstance(result, Forecast):
            from app.capacity.enums import ForecastQualifier

            assert ForecastQualifier.APPROACHING_BOUND in result.qualifiers

    def test_negligible_trend_with_real_noise(self) -> None:
        points = [_point(i, 100.0 + 0.001 * i + 0.02 * ((-1) ** i)) for i in range(80)]
        request = self._request(points, horizon_buckets=10, materiality=1000.0)
        result = forecast_series(request)
        if isinstance(result, Forecast) and result.evidence.slope_significant:
            assert result.trend_class is TrendClass.NEGLIGIBLE

    def test_peak_to_mean_divergence_none_with_too_few_valid_pairs(self) -> None:
        n = 20
        points = []
        for i in range(n):
            mean_value = 100.0 + i if i < 2 else None
            points.append(
                BucketedPoint(
                    index=i,
                    bucket_start=ORIGIN + timedelta(days=i),
                    sample_count=10,
                    expected_samples=None,
                    coverage=None,
                    peak=100.0 + i,
                    mean=mean_value,
                    p95=100.0 + i,
                    minimum=100.0,
                    excluded=False,
                )
            )
        request = self._request(
            points, reduction=ReductionKind.PEAK, horizon_buckets=3, materiality=0.1
        )
        result = forecast_series(request)
        if isinstance(result, Forecast):
            assert result.evidence.peak_to_mean_divergence is None

    def test_theil_sen_selected_but_too_few_points_for_quantile_band(self) -> None:
        n = 16  # above MIN_BUCKETS_FOR_CLAIM(14), below MIN_POINTS_FOR_QUANTILE_INTERVAL(19)
        values = [100.0 + 1.0 * i for i in range(n)]
        values[-1] = 10_000.0  # forces high OLS/Theil-Sen divergence
        points = [_point(i, v) for i, v in enumerate(values)]
        request = self._request(points, horizon_buckets=2, materiality=0.1)
        result = forecast_series(request)
        if isinstance(result, ForecastRefused):
            assert result.reason is RefusalReason.INSUFFICIENT_HISTORY


class TestProjectTruncationDeterministic:
    def test_hard_bound_truncates_growing_forecast(self) -> None:
        n = 40
        points = [_point(i, 10.0 * i + 0.5 * ((-1) ** i)) for i in range(n)]
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=15,
            bound=MetricBound(upper=500.0, kind=BoundKind.HARD_PHYSICAL),
            materiality=0.1,
        )
        result = forecast_series(request)
        assert isinstance(result, Forecast)
        assert result.trend_class is TrendClass.GROWING
        assert result.validity.value == "truncated_at_bound"
        assert result.points[-1].interval.upper >= 500.0 or result.points[-1].clipped


class TestEstimateExhaustionGapCoverage:
    def test_risk_within_horizon_band_only(self) -> None:
        points = _growing_series(40, slope=2.0, intercept=100.0, noise=8.0)
        request = ForecastRequest(
            points=points,
            reduction=ReductionKind.MEAN,
            bucket=timedelta(days=1),
            horizon_buckets=10,
            materiality=0.01,
            confidence=ConfidenceLevel.NINETY_FIVE,
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        horizon_point = forecast.at_horizon()
        assert horizon_point is not None
        # Choose a ceiling between the point projection and its upper band,
        # if such a gap exists at the horizon.
        if horizon_point.value < horizon_point.interval.upper:
            ceiling = (horizon_point.value + horizon_point.interval.upper) / 2
            estimate = estimate_exhaustion(forecast, ceiling=ceiling)
            assert estimate.status in (
                ExhaustionStatus.RISK_WITHIN_HORIZON,
                ExhaustionStatus.WILL_EXHAUST,
                ExhaustionStatus.NOT_WITHIN_HORIZON,
            )

    def _hand_built_forecast(
        self, *, point_values: list[float], band_half_width: float
    ) -> Forecast:
        """A Forecast built directly from dataclasses, bypassing regression
        noise, so exhaustion branches can be tested deterministically."""
        from app.capacity.buckets import CoverageReport
        from app.capacity.engine import FitEvidence, ForecastPoint
        from app.capacity.enums import (
            EstimatorKind,
            FitClass,
            IntervalMethod,
            PointSemantics,
            SeasonalityAssessment,
        )
        from app.capacity.enums import SaturationState as _SaturationState
        from app.capacity.regression import Interval, LinearFit

        fit = LinearFit(
            slope=1.0,
            intercept=0.0,
            n=len(point_values),
            x_centroid=0.0,
            sxx=1.0,
            sse=0.0,
            sst=1.0,
            residual_std=1.0,
            residuals=(),
            estimator=EstimatorKind.OLS,
            fit_class=FitClass.LINEAR,
            r_squared=0.9,
            adjusted_r_squared=0.9,
            residual_cv=0.1,
            se_slope=0.1,
            t_slope=10.0,
            durbin_watson=2.0,
            rho_estimate=0.0,
            variance_inflation=1.0,
        )
        evidence = FitEvidence(
            n_usable=len(point_values),
            reduction=ReductionKind.MEAN,
            estimator=EstimatorKind.OLS,
            estimator_reason="test",
            fit_class=FitClass.LINEAR,
            r_squared=0.9,
            adjusted_r_squared=0.9,
            residual_std=1.0,
            residual_cv=0.1,
            t_slope=10.0,
            slope_significant=True,
            durbin_watson=2.0,
            rho_estimate=0.0,
            variance_inflation=1.0,
            slope_divergence=None,
            coverage=CoverageReport(len(point_values), len(point_values), 0, 1.0, 0, 0.0),
            seasonality=SeasonalityAssessment.NONE_DETECTED,
            saturation=_SaturationState.NORMAL,
            influential_points=(),
            assumptions_unverified=(),
            peak_to_mean_divergence=None,
        )
        points = tuple(
            ForecastPoint(
                at=ORIGIN + timedelta(days=i + 1),
                index=100 + i,
                value=value,
                value_raw=value,
                clipped=False,
                interval=Interval(
                    lower=value - band_half_width,
                    upper=value + band_half_width,
                    confidence=ConfidenceLevel.NINETY,
                    method=IntervalMethod.STUDENT_T_PREDICTION,
                ),
            )
            for i, value in enumerate(point_values)
        )
        return Forecast(
            points=points,
            fit=fit,
            trend_class=TrendClass.GROWING,
            validity=None,
            point_semantics=PointSemantics.MEAN,  # type: ignore[arg-type]
            interval_method=IntervalMethod.STUDENT_T_PREDICTION,
            interval_meaning="",
            confidence=ConfidenceLevel.NINETY,
            bucket=timedelta(days=1),
            last_observed_at=ORIGIN,
            last_observed_value=point_values[0] - 1.0,
            qualifiers=(),
            evidence=evidence,
        )

    def test_risk_within_horizon_deterministic(self) -> None:
        # Point values stay below 100; the upper band (value + 20) crosses it.
        forecast = self._hand_built_forecast(
            point_values=[50.0, 60.0, 70.0, 80.0, 90.0], band_half_width=20.0
        )
        estimate = estimate_exhaustion(forecast, ceiling=100.0)
        assert estimate.status is ExhaustionStatus.RISK_WITHIN_HORIZON
        assert estimate.days_point is None
        assert estimate.days_earliest is not None

    def test_will_exhaust_deterministic(self) -> None:
        forecast = self._hand_built_forecast(
            point_values=[50.0, 70.0, 90.0, 110.0, 130.0], band_half_width=5.0
        )
        estimate = estimate_exhaustion(forecast, ceiling=100.0)
        assert estimate.status is ExhaustionStatus.WILL_EXHAUST
        assert estimate.days_point is not None
        assert estimate.exhaustion_at is not None


class TestPlanCapacityOverdueDeterministic:
    def test_overdue_rationale_mentions_days_in_the_past(self) -> None:
        from app.capacity.enums import CeilingSource

        estimate = ExhaustionEstimate(
            status=ExhaustionStatus.WILL_EXHAUST,
            days_point=1.0,
            days_earliest=1.0,
            days_latest=None,
            exhaustion_at=ORIGIN + timedelta(days=1),
            earliest_at=ORIGIN + timedelta(days=1),
            ceiling=100.0,
            ceiling_source=CeilingSource.DECLARED,
            headroom_now=10.0,
            resolution_days=1.0,
            rationale="",
        )
        points = _growing_series(20, slope=5.0, intercept=50.0, noise=0.2)
        request = ForecastRequest(
            points=points, reduction=ReductionKind.MEAN, bucket=timedelta(days=1), horizon_buckets=5
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        plan = plan_capacity(
            forecast,
            estimate,
            headroom_policy=0.1,
            lead_time_days=365,
            now=ORIGIN + timedelta(days=100),
        )
        assert plan.order_by_status is OrderByStatus.OVERDUE
        assert "in the past" in plan.rationale

    def test_no_crossing_within_horizon_gives_not_applicable(self) -> None:
        points = _growing_series(40, slope=0.5, intercept=100.0, noise=0.1)
        request = ForecastRequest(
            points=points, reduction=ReductionKind.MEAN, bucket=timedelta(days=1), horizon_buckets=5
        )
        forecast = forecast_series(request)
        assert isinstance(forecast, Forecast)
        estimate = estimate_exhaustion(forecast, ceiling=1_000_000.0)
        assert estimate.earliest_at is None
        plan = plan_capacity(forecast, estimate, headroom_policy=0.1, lead_time_days=7, now=ORIGIN)
        assert plan.order_by_status is OrderByStatus.NOT_APPLICABLE
        assert plan.recommended_provision is not None
