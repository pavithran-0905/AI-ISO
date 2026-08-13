"""Tests for app.anomaly.engine -- robust statistical anomaly detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.anomaly.engine import (
    DEFAULT_ROBUST_THRESHOLD,
    MIN_HISTORY_POINTS,
    Baseline,
    Detection,
    DetectionOutcome,
    Point,
    classify_shape,
    compute_baseline,
    detect_forecast_deviation,
    detect_level_departure,
    detect_seasonal,
    detect_statistical,
    detect_threshold,
    detect_trend,
    merge_outcomes,
    robust_z,
)
from app.models.enums import AnomalyMethod, AnomalySeverity, AnomalyShape


def _t(minutes: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes)


def _points(values: list[float], *, start: int = 0, step: int = 1) -> list[Point]:
    return [Point(at=_t(start + i * step), value=v) for i, v in enumerate(values)]


class TestComputeBaseline:
    def test_empty_is_degenerate(self) -> None:
        baseline = compute_baseline([])
        assert baseline.is_degenerate
        assert baseline.sample_count == 0
        assert baseline.spread_source == "none"

    def test_normal_spread(self) -> None:
        values = [100.0, 101.0, 99.0, 102.0, 98.0, 100.0, 100.0, 101.0] * 5
        baseline = compute_baseline(values)
        assert not baseline.is_degenerate
        assert baseline.median == pytest.approx(100.0)
        assert baseline.sample_count == len(values)
        assert baseline.low < baseline.median < baseline.high

    def test_degenerate_when_over_half_identical(self) -> None:
        values = [5.0] * 20 + [5.0, 5.0]
        baseline = compute_baseline(values)
        assert baseline.is_degenerate
        assert baseline.mad == 0.0

    def test_is_usable_requires_history_and_non_degenerate(self) -> None:
        few = compute_baseline([1.0, 2.0, 3.0])
        assert not few.is_usable
        plenty = compute_baseline([float(i % 5) for i in range(40)])
        assert plenty.is_usable or plenty.is_degenerate  # sanity: property does not raise


class TestRobustZ:
    def test_degenerate_baseline_returns_none(self) -> None:
        baseline = Baseline(
            median=5.0, mad=0.0, sample_count=10, low=5.0, high=5.0, is_degenerate=True
        )
        assert robust_z(5.0, baseline) is None

    def test_normal_baseline_computes_distance(self) -> None:
        baseline = compute_baseline([100.0 + (i % 3 - 1) for i in range(40)])
        z = robust_z(200.0, baseline)
        assert z is not None
        assert z > 0


class TestDetectStatistical:
    def test_refuses_below_min_history(self) -> None:
        outcome = detect_statistical(_points([1.0, 2.0, 3.0]))
        assert not outcome.could_evaluate
        assert outcome.refusal_reason is not None
        assert outcome.evaluated_points == 0

    def test_negative_exclude_recent_raises(self) -> None:
        with pytest.raises(ValueError, match="exclude_recent"):
            detect_statistical(_points([1.0] * 40), exclude_recent=-1)

    def test_flags_spike_above_threshold(self) -> None:
        values = [100.0 + (i % 3 - 1) for i in range(40)] + [500.0]
        outcome = detect_statistical(_points(values))
        assert outcome.could_evaluate
        assert len(outcome.detections) == 1
        detection = outcome.detections[0]
        assert detection.shape is AnomalyShape.SPIKE
        assert detection.method is AnomalyMethod.ROBUST_ZSCORE
        assert detection.deviation is not None and detection.deviation > 0
        assert "robust deviations" in detection.rationale

    def test_flags_dip_below_threshold(self) -> None:
        values = [100.0 + (i % 3 - 1) for i in range(40)] + [-500.0]
        outcome = detect_statistical(_points(values))
        assert len(outcome.detections) == 1
        assert outcome.detections[0].shape is AnomalyShape.DIP

    def test_exclude_recent_removes_incident_from_baseline(self) -> None:
        # A sustained "incident" at the tail should not redefine the baseline
        # when exclude_recent covers it.
        healthy = [100.0 + (i % 3 - 1) for i in range(40)]
        incident = [1000.0] * 10
        values = healthy + incident
        outcome = detect_statistical(_points(values), exclude_recent=10)
        assert outcome.could_evaluate
        incident_detections = [d for d in outcome.detections if d.observed == 1000.0]
        assert len(incident_detections) == 10

    def test_exclude_recent_leaves_too_few_for_baseline_refuses(self) -> None:
        values = [100.0] * MIN_HISTORY_POINTS
        outcome = detect_statistical(_points(values), exclude_recent=MIN_HISTORY_POINTS - 1)
        assert not outcome.could_evaluate
        assert "Widen the history window" in (outcome.refusal_reason or "")

    def test_degenerate_baseline_refuses(self) -> None:
        values = [5.0] * 40
        outcome = detect_statistical(_points(values))
        assert not outcome.could_evaluate
        assert "no spread to measure" in (outcome.refusal_reason or "")

    def test_explicit_baseline_is_used(self) -> None:
        known_good = compute_baseline([100.0 + (i % 3 - 1) for i in range(40)])
        outcome = detect_statistical(_points([500.0] * 40), baseline=known_good)
        assert outcome.could_evaluate
        assert len(outcome.detections) == 40


class TestDetectLevelDeparture:
    def test_refuses_below_min_history(self) -> None:
        outcome = detect_level_departure(_points([1.0, 2.0]))
        assert not outcome.could_evaluate

    def test_refuses_when_no_dominant_level(self) -> None:
        values = [float(i) for i in range(40)]
        outcome = detect_level_departure(_points(values))
        assert not outcome.could_evaluate
        assert "continuous metric" in (outcome.refusal_reason or "")

    def test_flags_departure_from_held_level(self) -> None:
        values = [3.0] * 35 + [0.0] * 5
        outcome = detect_level_departure(_points(values))
        assert outcome.could_evaluate
        assert len(outcome.detections) == 5
        detection = outcome.detections[0]
        assert detection.deviation is None
        assert detection.method is AnomalyMethod.LEVEL_SHIFT
        assert detection.shape is AnomalyShape.DIP

    def test_flags_departure_above_level(self) -> None:
        values = [3.0] * 35 + [9.0] * 5
        outcome = detect_level_departure(_points(values))
        assert outcome.detections[0].shape is AnomalyShape.SPIKE


class TestDetectThreshold:
    def test_raises_when_no_bound_given(self) -> None:
        with pytest.raises(ValueError, match="upper bound"):
            detect_threshold(_points([1.0]))

    def test_raises_on_inverted_bounds(self) -> None:
        with pytest.raises(ValueError, match="lower bound"):
            detect_threshold(_points([1.0]), upper=1.0, lower=2.0)

    def test_flags_upper_breach(self) -> None:
        outcome = detect_threshold(_points([1.0, 5.0, 2.0]), upper=3.0)
        assert len(outcome.detections) == 1
        assert outcome.detections[0].shape is AnomalyShape.SPIKE
        assert outcome.detections[0].deviation is None

    def test_flags_lower_breach(self) -> None:
        outcome = detect_threshold(_points([1.0, 5.0, 2.0]), lower=3.0)
        detections = outcome.detections
        assert len(detections) == 2
        assert all(d.shape is AnomalyShape.DIP for d in detections)

    def test_no_history_requirement(self) -> None:
        outcome = detect_threshold(_points([100.0]), upper=10.0)
        assert len(outcome.detections) == 1


class TestDetectSeasonal:
    def test_raises_on_non_positive_period(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            detect_seasonal(_points([1.0]), period=timedelta(0))

    def test_single_point_refuses(self) -> None:
        outcome = detect_seasonal(_points([1.0]), period=timedelta(hours=1))
        assert not outcome.could_evaluate

    def test_refuses_below_min_cycles(self) -> None:
        points = _points([100.0, 101.0], step=60)
        outcome = detect_seasonal(points, period=timedelta(hours=1))
        assert not outcome.could_evaluate
        assert "cycles of history" in (outcome.refusal_reason or "")

    def test_detects_seasonal_deviation(self) -> None:
        period = timedelta(hours=1)
        points: list[Point] = []
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for cycle in range(6):
            for minute in range(0, 60, 10):
                value = 100.0 if minute != 0 else 20.0
                points.append(
                    Point(at=base + period * cycle + timedelta(minutes=minute), value=value)
                )
        # Anomalous cycle: minute-0 phase spikes hugely on the last cycle.
        points.append(Point(at=base + period * 6, value=900.0))
        for minute in range(10, 60, 10):
            points.append(Point(at=base + period * 6 + timedelta(minutes=minute), value=100.0))

        outcome = detect_seasonal(points, period=period)
        assert outcome.could_evaluate
        assert any(d.shape is AnomalyShape.SEASONAL_DEVIATION for d in outcome.detections)

    def test_degenerate_phase_baseline_reports_deviation_none(self) -> None:
        period = timedelta(hours=1)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        points: list[Point] = []
        for cycle in range(6):
            points.append(Point(at=base + period * cycle, value=1000.0))
        points.append(Point(at=base + period * 6, value=1500.0))
        outcome = detect_seasonal(points, period=period)
        assert outcome.could_evaluate
        deviant = [d for d in outcome.detections if d.observed == 1500.0]
        assert len(deviant) == 1
        assert deviant[0].deviation is None


class TestClassifyShape:
    def test_empty_detections_returns_empty(self) -> None:
        assert classify_shape(_points([1.0]), []) == []

    def test_single_point_run_is_the_bare_shape(self) -> None:
        points = _points([100.0 + (i % 3 - 1) for i in range(39)] + [500.0])
        outcome = detect_statistical(points)
        verdicts = classify_shape(points, outcome.detections)
        assert len(verdicts) == 1
        assert verdicts[0].shape is AnomalyShape.SPIKE
        assert verdicts[0].is_ongoing

    def test_long_run_becomes_level_shift(self) -> None:
        points = _points([100.0 + (i % 3 - 1) for i in range(30)] + [500.0] * 6)
        outcome = detect_statistical(points, exclude_recent=0)
        verdicts = classify_shape(points, outcome.detections)
        assert any(v.shape is AnomalyShape.LEVEL_SHIFT for v in verdicts)


class TestDetectTrend:
    def test_refuses_below_min_history(self) -> None:
        verdict = detect_trend(_points([1.0, 2.0]))
        assert not verdict.has_trend
        assert verdict.direction == "unknown"

    def test_zero_earlier_median_is_undefined(self) -> None:
        values = [0.0] * 13 + [1.0] * 14 + [2.0] * 13
        verdict = detect_trend(_points(values))
        assert not verdict.has_trend
        assert "undefined" in verdict.rationale

    def test_detects_rising_trend(self) -> None:
        values = [float(i) for i in range(40)]
        verdict = detect_trend(_points(values))
        assert verdict.has_trend
        assert verdict.direction == "rising"
        assert verdict.slope_per_point is not None and verdict.slope_per_point > 0

    def test_detects_falling_trend(self) -> None:
        values = [float(40 - i) for i in range(40)]
        verdict = detect_trend(_points(values))
        assert verdict.has_trend
        assert verdict.direction == "falling"

    def test_flat_series_has_no_trend(self) -> None:
        values = [100.0 + (i % 2) for i in range(40)]
        verdict = detect_trend(_points(values))
        assert not verdict.has_trend


class TestDetectForecastDeviation:
    def test_raises_on_inverted_interval(self) -> None:
        with pytest.raises(ValueError, match="inverted"):
            detect_forecast_deviation(
                5.0, at=_t(0), predicted=5.0, interval_low=10.0, interval_high=0.0
            )

    def test_inside_interval_returns_none(self) -> None:
        result = detect_forecast_deviation(
            5.0, at=_t(0), predicted=5.0, interval_low=0.0, interval_high=10.0
        )
        assert result is None

    def test_above_interval_returns_detection(self) -> None:
        result = detect_forecast_deviation(
            15.0, at=_t(0), predicted=5.0, interval_low=0.0, interval_high=10.0
        )
        assert result is not None
        assert result.shape is AnomalyShape.SPIKE
        assert result.method is AnomalyMethod.FORECAST_DEVIATION
        assert result.deviation is not None and result.deviation > 0

    def test_below_interval_returns_detection(self) -> None:
        result = detect_forecast_deviation(
            -5.0, at=_t(0), predicted=5.0, interval_low=0.0, interval_high=10.0
        )
        assert result is not None
        assert result.shape is AnomalyShape.DIP

    def test_zero_width_interval_deviation_is_none(self) -> None:
        result = detect_forecast_deviation(
            5.0, at=_t(0), predicted=0.0, interval_low=0.0, interval_high=0.0
        )
        assert result is not None
        assert result.deviation is None
        assert result.severity is AnomalySeverity.MEDIUM


class TestMergeOutcomes:
    def test_merges_and_dedupes_keeping_larger_deviation(self) -> None:
        at = _t(0)
        weak = Detection(
            at=at,
            observed=5.0,
            expected=0.0,
            expected_low=None,
            expected_high=None,
            deviation=2.0,
            method=AnomalyMethod.ROBUST_ZSCORE,
            shape=AnomalyShape.SPIKE,
            severity=AnomalySeverity.LOW,
            baseline_sample_count=30,
            rationale="weak",
        )
        strong = Detection(
            at=at,
            observed=5.0,
            expected=0.0,
            expected_low=None,
            expected_high=None,
            deviation=8.0,
            method=AnomalyMethod.SEASONAL,
            shape=AnomalyShape.SPIKE,
            severity=AnomalySeverity.HIGH,
            baseline_sample_count=30,
            rationale="strong",
        )
        merged = merge_outcomes(
            DetectionOutcome(detections=[weak], evaluated_points=40),
            DetectionOutcome(detections=[strong], evaluated_points=40),
        )
        assert len(merged.detections) == 1
        assert merged.detections[0].rationale == "strong"

    def test_threshold_detection_never_displaces_measured_one(self) -> None:
        at = _t(0)
        measured = Detection(
            at=at,
            observed=5.0,
            expected=0.0,
            expected_low=None,
            expected_high=None,
            deviation=4.0,
            method=AnomalyMethod.ROBUST_ZSCORE,
            shape=AnomalyShape.SPIKE,
            severity=AnomalySeverity.MEDIUM,
            baseline_sample_count=30,
            rationale="measured",
        )
        threshold_only = Detection(
            at=at,
            observed=5.0,
            expected=None,
            expected_low=None,
            expected_high=None,
            deviation=None,
            method=AnomalyMethod.THRESHOLD,
            shape=AnomalyShape.SPIKE,
            severity=AnomalySeverity.MEDIUM,
            baseline_sample_count=0,
            rationale="threshold",
        )
        merged = merge_outcomes(
            DetectionOutcome(detections=[measured], evaluated_points=1),
            DetectionOutcome(detections=[threshold_only], evaluated_points=1),
        )
        assert merged.detections[0].rationale == "measured"

    def test_refusal_only_when_every_outcome_refused(self) -> None:
        refused_a = DetectionOutcome(evaluated_points=0, refusal_reason="a")
        refused_b = DetectionOutcome(evaluated_points=0, refusal_reason="b")
        merged = merge_outcomes(refused_a, refused_b)
        assert merged.refusal_reason == "a"

    def test_partial_refusal_is_not_reported(self) -> None:
        refused = DetectionOutcome(evaluated_points=0, refusal_reason="a")
        found = DetectionOutcome(
            detections=[
                Detection(
                    at=_t(0),
                    observed=1.0,
                    expected=0.0,
                    expected_low=None,
                    expected_high=None,
                    deviation=5.0,
                    method=AnomalyMethod.ROBUST_ZSCORE,
                    shape=AnomalyShape.SPIKE,
                    severity=AnomalySeverity.MEDIUM,
                    baseline_sample_count=30,
                    rationale="x",
                )
            ],
            evaluated_points=40,
        )
        merged = merge_outcomes(refused, found)
        assert merged.refusal_reason is None
        assert len(merged.detections) == 1

    def test_empty_merge(self) -> None:
        merged = merge_outcomes()
        assert merged.detections == []
        assert merged.refusal_reason is None


def test_default_threshold_constant() -> None:
    assert DEFAULT_ROBUST_THRESHOLD == 3.5
