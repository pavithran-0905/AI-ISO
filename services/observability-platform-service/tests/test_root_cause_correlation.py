"""Tests for app.root_cause.correlation -- Spearman correlation, lag search."""

from __future__ import annotations

import pytest

from app.root_cause.correlation import (
    Series,
    correlate,
    detect_platform_gaps,
    difference,
    expected_false_positives,
    holm_adjust,
    jaccard,
    lag_one_autocorrelation,
    rho_critical,
    spearman,
    symptom_specificity,
)
from app.root_cause.enums import Unmeasurable


def _series(
    name: str,
    values: list[float],
    *,
    observed: list[bool] | None = None,
    bucket_seconds: float = 60.0,
) -> Series:
    return Series(
        service=name,
        values=tuple(values),
        observed=tuple(observed if observed is not None else [True] * len(values)),
        bucket_seconds=bucket_seconds,
    )


class TestRhoCritical:
    def test_below_min_paired_is_unity(self) -> None:
        assert rho_critical(3) == 1.0

    def test_floors_at_min_rho(self) -> None:
        assert rho_critical(1000) == 0.50

    def test_scales_with_n(self) -> None:
        assert rho_critical(10) > rho_critical(100)


class TestSeries:
    def test_mismatched_length_raises(self) -> None:
        with pytest.raises(ValueError, match="mask entries"):
            Series(service="a", values=(1.0, 2.0), observed=(True,), bucket_seconds=60.0)

    def test_active_buckets_requires_observed_and_positive(self) -> None:
        series = _series("a", [0.0, 1.0, 2.0], observed=[True, True, False])
        assert series.active_buckets == frozenset({1})


class TestSpearman:
    def test_too_few_points_returns_none(self) -> None:
        assert spearman([1.0], [1.0]) is None

    def test_perfect_positive_correlation(self) -> None:
        result = spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0])
        assert result == pytest.approx(1.0)

    def test_perfect_negative_correlation(self) -> None:
        result = spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0])
        assert result == pytest.approx(-1.0)

    def test_no_spread_returns_none(self) -> None:
        assert spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None

    def test_tied_ranks_are_averaged(self) -> None:
        result = spearman([1.0, 1.0, 2.0, 3.0], [10.0, 10.0, 20.0, 30.0])
        assert result == pytest.approx(1.0)


class TestLagOneAutocorrelation:
    def test_too_few_points_returns_none(self) -> None:
        assert lag_one_autocorrelation([1.0, 2.0]) is None

    def test_computes_correlation(self) -> None:
        result = lag_one_autocorrelation([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result == pytest.approx(1.0)


class TestDifference:
    def test_first_differences(self) -> None:
        assert difference([1.0, 3.0, 6.0]) == [2.0, 3.0]


class TestJaccard:
    def test_both_empty_is_unmeasurable(self) -> None:
        value, reason = jaccard(frozenset(), frozenset())
        assert value is None
        assert reason is Unmeasurable.BOTH_SERIES_NEVER_ACTIVE

    def test_full_overlap(self) -> None:
        value, reason = jaccard(frozenset({1, 2}), frozenset({1, 2}))
        assert value == 1.0
        assert reason is None

    def test_partial_overlap(self) -> None:
        value, _ = jaccard(frozenset({1, 2}), frozenset({2, 3}))
        assert value == pytest.approx(1 / 3)


class TestCorrelate:
    def test_mismatched_bucket_seconds_raises(self) -> None:
        a = _series("a", [1.0] * 10, bucket_seconds=60.0)
        b = _series("b", [1.0] * 10, bucket_seconds=30.0)
        with pytest.raises(ValueError, match="Cannot correlate"):
            correlate(a, b)

    def test_too_few_paired_buckets(self) -> None:
        a = _series("a", [1.0, 2.0, 3.0])
        b = _series("b", [1.0, 2.0, 3.0])
        result = correlate(a, b)
        assert result.unmeasurable is Unmeasurable.TOO_FEW_PAIRED_BUCKETS
        assert not result.is_measured

    def test_correlated_series_at_zero_lag(self) -> None:
        n = 20
        values = [float(i % 7) for i in range(n)]
        a = _series("a", values)
        b = _series("b", [v * 2 for v in values])
        result = correlate(a, b)
        assert result.is_measured
        assert result.coefficient == pytest.approx(1.0)
        assert result.lag_buckets == 0

    def test_lagged_correlation_found(self) -> None:
        n = 30
        base = [float(i % 5) for i in range(n)]
        a = _series("a", base)
        shifted = [0.0, 0.0, *base[:-2]]
        b = _series("b", shifted)
        result = correlate(a, b, max_lag=5)
        assert result.is_measured

    def test_constant_series_is_unmeasurable(self) -> None:
        n = 10
        a = _series("a", [5.0] * n)
        b = _series("b", [5.0] * n)
        result = correlate(a, b)
        assert result.unmeasurable is Unmeasurable.ONE_SERIES_CONSTANT

    def test_excluded_buckets_counted_from_gaps(self) -> None:
        n = 12
        a = _series("a", [float(i) for i in range(n)], observed=[i != 0 for i in range(n)])
        b = _series("b", [float(i) for i in range(n)])
        result = correlate(a, b)
        assert result.excluded_buckets >= 1

    def test_autocorrelated_series_gets_differenced(self) -> None:
        n = 20
        # Strong trend => high lag-1 autocorrelation => differenced=True.
        a = _series("a", [float(i) for i in range(n)])
        b = _series("b", [float(i) * 1.5 for i in range(n)])
        result = correlate(a, b)
        assert result.differenced


class TestHolmAdjust:
    def test_adjusts_and_marks_significance(self) -> None:
        n = 30
        values = [float(i % 7) for i in range(n)]
        strong_a = _series("a", values)
        strong_b = _series("b", values)
        result = correlate(strong_a, strong_b)
        adjusted = holm_adjust([result])
        assert len(adjusted) == 1
        assert adjusted[0].adjusted_p_value is not None

    def test_unmeasured_results_pass_through(self) -> None:
        a = _series("a", [1.0, 2.0])
        b = _series("b", [1.0, 2.0])
        result = correlate(a, b)
        adjusted = holm_adjust([result])
        assert adjusted[0].unmeasurable is Unmeasurable.TOO_FEW_PAIRED_BUCKETS

    def test_empty_results(self) -> None:
        assert holm_adjust([]) == ()


class TestExpectedFalsePositives:
    def test_scales_with_comparisons(self) -> None:
        assert expected_false_positives(100) == pytest.approx(1.0)


class TestDetectPlatformGaps:
    def test_empty_series_returns_empty(self) -> None:
        assert detect_platform_gaps([]) == ()

    def test_no_gaps_when_all_observed(self) -> None:
        series = [_series("a", [1.0, 2.0]), _series("b", [1.0, 2.0])]
        assert detect_platform_gaps(series) == ()

    def test_detects_majority_silent_bucket(self) -> None:
        series = [
            _series("a", [1.0, 1.0], observed=[False, True]),
            _series("b", [1.0, 1.0], observed=[False, True]),
            _series("c", [1.0, 1.0], observed=[True, True]),
        ]
        gaps = detect_platform_gaps(series)
        assert 0 in gaps


class TestSymptomSpecificity:
    def test_none_when_no_baseline(self) -> None:
        assert symptom_specificity(5, 0) is None

    def test_computes_specificity(self) -> None:
        assert symptom_specificity(10, 100) == pytest.approx(0.9)
