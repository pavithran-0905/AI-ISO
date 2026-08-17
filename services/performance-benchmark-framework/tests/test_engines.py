"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import (
    performance_score,
    regression_free_rate,
    slo_compliance_rate,
    success_rate,
)
from app.baseline.engine import compute_baseline_from_samples, is_baseline_stale
from app.benchmark.engine import TransitionRefusal, is_job_stuck, validate_transition
from app.capacity.engine import is_threshold_breached, periods_until_threshold, project_value
from app.latency.engine import compute_percentiles
from app.models.enums import (
    BenchmarkRunStatus,
    BenchmarkType,
    OptimizationCategory,
    RegressionSeverity,
    RegressionType,
    SliType,
)
from app.optimization.engine import category_for_regression, compute_impact_score, is_high_impact
from app.regression.engine import (
    classify_severity,
    infer_regression_type,
    is_improvement,
    is_regression,
    percent_change,
)
from app.slo.engine import higher_is_better_for, is_slo_compliant
from app.throughput.engine import compute_requests_per_second, is_throughput_drop
from app.utilization.engine import classify_utilization, is_bottleneck

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


class TestBenchmarkEngine:
    def test_pending_to_running(self) -> None:
        assert validate_transition(
            BenchmarkRunStatus.PENDING, BenchmarkRunStatus.RUNNING
        ).is_allowed

    def test_succeeded_is_terminal(self) -> None:
        result = validate_transition(BenchmarkRunStatus.SUCCEEDED, BenchmarkRunStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_running_to_failed_allowed(self) -> None:
        assert validate_transition(BenchmarkRunStatus.RUNNING, BenchmarkRunStatus.FAILED).is_allowed

    def test_invalid_transition(self) -> None:
        result = validate_transition(BenchmarkRunStatus.PENDING, BenchmarkRunStatus.SUCCEEDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_job_stuck_past_max_age(self) -> None:
        assert is_job_stuck(
            BenchmarkRunStatus.RUNNING,
            started_at=NOW - timedelta(hours=5),
            now=NOW,
            max_age_hours=4,
        )

    def test_job_not_stuck_within_max_age(self) -> None:
        assert not is_job_stuck(
            BenchmarkRunStatus.RUNNING,
            started_at=NOW - timedelta(hours=1),
            now=NOW,
            max_age_hours=4,
        )

    def test_job_not_stuck_when_pending(self) -> None:
        assert not is_job_stuck(
            BenchmarkRunStatus.PENDING, started_at=None, now=NOW, max_age_hours=4
        )


class TestRegressionEngine:
    def test_percent_change_basic(self) -> None:
        assert percent_change(baseline=100.0, current=120.0) == pytest.approx(20.0)

    def test_percent_change_zero_baseline_zero_current(self) -> None:
        assert percent_change(baseline=0.0, current=0.0) == 0.0

    def test_percent_change_zero_baseline_positive_current(self) -> None:
        assert percent_change(baseline=0.0, current=5.0) == 100.0

    def test_percent_change_zero_baseline_negative_current(self) -> None:
        assert percent_change(baseline=0.0, current=-5.0) == -100.0

    def test_latency_regression_lower_is_better(self) -> None:
        assert is_regression(
            baseline=100.0, current=150.0, higher_is_better=False, warning_threshold_percent=10.0
        )

    def test_latency_improvement_lower_is_better(self) -> None:
        assert is_improvement(
            baseline=100.0, current=80.0, higher_is_better=False, improvement_threshold_percent=10.0
        )

    def test_throughput_regression_higher_is_better(self) -> None:
        assert is_regression(
            baseline=1000.0, current=800.0, higher_is_better=True, warning_threshold_percent=10.0
        )

    def test_throughput_improvement_higher_is_better(self) -> None:
        assert is_improvement(
            baseline=1000.0,
            current=1200.0,
            higher_is_better=True,
            improvement_threshold_percent=10.0,
        )

    def test_no_regression_within_tolerance(self) -> None:
        assert not is_regression(
            baseline=100.0, current=105.0, higher_is_better=False, warning_threshold_percent=10.0
        )

    def test_severity_low(self) -> None:
        assert (
            classify_severity(regression_percent=5.0, critical_threshold_percent=25.0)
            == RegressionSeverity.LOW
        )

    def test_severity_medium(self) -> None:
        assert (
            classify_severity(regression_percent=15.0, critical_threshold_percent=25.0)
            == RegressionSeverity.MEDIUM
        )

    def test_severity_high(self) -> None:
        assert (
            classify_severity(regression_percent=20.0, critical_threshold_percent=25.0)
            == RegressionSeverity.HIGH
        )

    def test_severity_critical(self) -> None:
        assert (
            classify_severity(regression_percent=30.0, critical_threshold_percent=25.0)
            == RegressionSeverity.CRITICAL
        )

    def test_severity_zero_critical_threshold(self) -> None:
        assert (
            classify_severity(regression_percent=1.0, critical_threshold_percent=0.0)
            == RegressionSeverity.CRITICAL
        )

    def test_infer_latency_by_name(self) -> None:
        assert (
            infer_regression_type(
                metric_name="p99_latency_ms", benchmark_type=BenchmarkType.PLATFORM
            )
            == RegressionType.LATENCY
        )

    def test_infer_throughput_by_name(self) -> None:
        assert (
            infer_regression_type(metric_name="requests_rps", benchmark_type=BenchmarkType.PLATFORM)
            == RegressionType.THROUGHPUT
        )

    def test_infer_via_benchmark_type_fallback(self) -> None:
        assert (
            infer_regression_type(metric_name="score", benchmark_type=BenchmarkType.DATABASE)
            == RegressionType.DATABASE
        )

    def test_infer_default_fallback(self) -> None:
        assert (
            infer_regression_type(metric_name="score", benchmark_type=BenchmarkType.AI)
            == RegressionType.LATENCY
        )


class TestSloEngine:
    def test_latency_lower_is_better(self) -> None:
        assert higher_is_better_for(SliType.LATENCY) is False

    def test_availability_higher_is_better(self) -> None:
        assert higher_is_better_for(SliType.AVAILABILITY) is True

    def test_custom_defaults_true(self) -> None:
        assert higher_is_better_for(SliType.CUSTOM) is True

    def test_latency_compliant(self) -> None:
        assert is_slo_compliant(actual_value=90.0, target_value=100.0, sli_type=SliType.LATENCY)

    def test_latency_non_compliant(self) -> None:
        assert not is_slo_compliant(
            actual_value=120.0, target_value=100.0, sli_type=SliType.LATENCY
        )

    def test_availability_compliant(self) -> None:
        assert is_slo_compliant(
            actual_value=99.95, target_value=99.9, sli_type=SliType.AVAILABILITY
        )

    def test_availability_non_compliant(self) -> None:
        assert not is_slo_compliant(
            actual_value=99.5, target_value=99.9, sli_type=SliType.AVAILABILITY
        )

    def test_explicit_direction_overrides_default(self) -> None:
        assert not is_slo_compliant(
            actual_value=90.0, target_value=100.0, sli_type=SliType.CUSTOM, higher_is_better=True
        )


class TestCapacityEngine:
    def test_project_value_grows(self) -> None:
        assert project_value(
            current_value=100.0, growth_rate_percent=10.0, periods=1
        ) == pytest.approx(110.0)

    def test_project_value_zero_periods(self) -> None:
        assert project_value(
            current_value=100.0, growth_rate_percent=10.0, periods=0
        ) == pytest.approx(100.0)

    def test_threshold_breached(self) -> None:
        assert is_threshold_breached(projected_value=95.0, threshold_value=90.0)

    def test_threshold_not_breached(self) -> None:
        assert not is_threshold_breached(projected_value=80.0, threshold_value=90.0)

    def test_periods_until_threshold_already_breached(self) -> None:
        assert (
            periods_until_threshold(
                current_value=95.0, growth_rate_percent=5.0, threshold_value=90.0
            )
            == 0.0
        )

    def test_periods_until_threshold_never_flat(self) -> None:
        assert (
            periods_until_threshold(
                current_value=50.0, growth_rate_percent=0.0, threshold_value=90.0
            )
            is None
        )

    def test_periods_until_threshold_positive(self) -> None:
        periods = periods_until_threshold(
            current_value=50.0, growth_rate_percent=10.0, threshold_value=90.0
        )
        assert periods is not None
        assert periods > 0


class TestOptimizationEngine:
    def test_impact_score_bounded(self) -> None:
        assert compute_impact_score(magnitude_percent=200.0) == 100.0

    def test_impact_score_scaled(self) -> None:
        assert compute_impact_score(magnitude_percent=20.0, category_weight=2.0) == pytest.approx(
            40.0
        )

    def test_high_impact_true(self) -> None:
        assert is_high_impact(60.0)

    def test_high_impact_false(self) -> None:
        assert not is_high_impact(10.0)

    def test_category_for_database_regression(self) -> None:
        assert category_for_regression(RegressionType.DATABASE) == OptimizationCategory.QUERY

    def test_category_default_infrastructure(self) -> None:
        assert (
            category_for_regression(RegressionType.LATENCY) == OptimizationCategory.INFRASTRUCTURE
        )


class TestLatencyEngine:
    def test_percentiles_reasonable(self) -> None:
        samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        percentiles = compute_percentiles(samples)
        assert 40.0 <= percentiles.p50_ms <= 60.0
        assert percentiles.max_ms == 100.0

    def test_percentiles_empty_honest_zero(self) -> None:
        percentiles = compute_percentiles([])
        assert percentiles.p50_ms == 0.0
        assert percentiles.max_ms == 0.0


class TestThroughputEngine:
    def test_rps_basic(self) -> None:
        assert compute_requests_per_second(request_count=100, duration_seconds=10.0) == 10.0

    def test_rps_zero_duration_honest_zero(self) -> None:
        assert compute_requests_per_second(request_count=100, duration_seconds=0.0) == 0.0

    def test_throughput_drop_detected(self) -> None:
        assert is_throughput_drop(current=80.0, previous=100.0, drop_threshold_percent=10.0)

    def test_throughput_drop_not_detected_small_dip(self) -> None:
        assert not is_throughput_drop(current=98.0, previous=100.0, drop_threshold_percent=10.0)

    def test_throughput_drop_zero_previous(self) -> None:
        assert not is_throughput_drop(current=10.0, previous=0.0, drop_threshold_percent=10.0)


class TestUtilizationEngine:
    def test_classify_ok(self) -> None:
        assert classify_utilization(50.0) == "ok"

    def test_classify_warning(self) -> None:
        assert classify_utilization(80.0) == "warning"

    def test_classify_bottleneck(self) -> None:
        assert classify_utilization(95.0) == "bottleneck"

    def test_is_bottleneck_true(self) -> None:
        assert is_bottleneck(95.0)

    def test_is_bottleneck_false(self) -> None:
        assert not is_bottleneck(50.0)


class TestBaselineEngine:
    def test_median_baseline(self) -> None:
        assert compute_baseline_from_samples([10.0, 20.0, 30.0]) == 20.0

    def test_empty_baseline_honest_zero(self) -> None:
        assert compute_baseline_from_samples([]) == 0.0

    def test_baseline_stale(self) -> None:
        assert is_baseline_stale(
            baseline_value=100.0, recent_median=150.0, staleness_threshold_percent=25.0
        )

    def test_baseline_not_stale(self) -> None:
        assert not is_baseline_stale(
            baseline_value=100.0, recent_median=105.0, staleness_threshold_percent=25.0
        )

    def test_baseline_stale_zero_baseline(self) -> None:
        assert is_baseline_stale(
            baseline_value=0.0, recent_median=5.0, staleness_threshold_percent=25.0
        )


class TestAnalyticsEngine:
    def test_success_rate_basic(self) -> None:
        assert success_rate(8, 10) == pytest.approx(0.8)

    def test_success_rate_empty_honest_zero(self) -> None:
        assert success_rate(0, 0) == 0.0

    def test_slo_compliance_rate_basic(self) -> None:
        assert slo_compliance_rate(9, 10) == pytest.approx(0.9)

    def test_slo_compliance_rate_vacuous(self) -> None:
        assert slo_compliance_rate(0, 0) == 1.0

    def test_regression_free_rate_basic(self) -> None:
        assert regression_free_rate(1, 10) == pytest.approx(0.9)

    def test_regression_free_rate_vacuous(self) -> None:
        assert regression_free_rate(0, 0) == 1.0

    def test_performance_score_average(self) -> None:
        score = performance_score(
            success_rate_value=0.9, slo_compliance_rate_value=1.0, regression_free_rate_value=0.8
        )
        assert score == pytest.approx((0.9 + 1.0 + 0.8) / 3)
