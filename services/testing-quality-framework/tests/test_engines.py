"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import failure_rate, flaky_rate, is_flaky, pass_rate, quality_score
from app.benchmark.engine import is_benchmark_regression, percent_change
from app.chaos.engine import classify_chaos_result, is_recovery_within_target
from app.contract.engine import classify_contract_compatibility, parse_semantic_version
from app.coverage.engine import coverage_delta, is_coverage_drop, is_coverage_sufficient
from app.models.enums import CheckResultStatus, QualityGateStatus
from app.models.enums import TestResultStatus as ResultStatus
from app.models.enums import TestRunStatus as RunStatus
from app.performance.engine import is_performance_regression, is_within_threshold
from app.pipeline.engine import TransitionRefusal, is_job_stuck, validate_transition
from app.quality_gates.engine import all_gates_passed, evaluate_gate
from app.security.engine import classify_security_result
from app.synthetic.engine import availability_percentage

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


class TestPipelineEngine:
    def test_pending_to_running(self) -> None:
        assert validate_transition(RunStatus.PENDING, RunStatus.RUNNING).is_allowed

    def test_failed_is_terminal(self) -> None:
        result = validate_transition(RunStatus.FAILED, RunStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_job_stuck_past_max_age(self) -> None:
        assert is_job_stuck(
            RunStatus.RUNNING, started_at=NOW - timedelta(hours=5), now=NOW, max_age_hours=4
        )

    def test_job_not_stuck_within_max_age(self) -> None:
        assert not is_job_stuck(
            RunStatus.RUNNING, started_at=NOW - timedelta(hours=1), now=NOW, max_age_hours=4
        )


class TestQualityGatesEngine:
    def test_higher_is_better_passes(self) -> None:
        assert evaluate_gate(value=95.0, threshold=90.0) == QualityGateStatus.PASSED

    def test_higher_is_better_fails(self) -> None:
        assert evaluate_gate(value=80.0, threshold=90.0) == QualityGateStatus.FAILED

    def test_lower_is_better_passes(self) -> None:
        assert (
            evaluate_gate(value=100.0, threshold=200.0, higher_is_better=False)
            == QualityGateStatus.PASSED
        )

    def test_all_gates_passed_true(self) -> None:
        assert all_gates_passed([QualityGateStatus.PASSED, QualityGateStatus.PASSED])

    def test_all_gates_passed_false(self) -> None:
        assert not all_gates_passed([QualityGateStatus.PASSED, QualityGateStatus.FAILED])


class TestCoverageEngine:
    def test_sufficient(self) -> None:
        assert is_coverage_sufficient(95.0, threshold=90.0)

    def test_insufficient(self) -> None:
        assert not is_coverage_sufficient(85.0, threshold=90.0)

    def test_delta(self) -> None:
        assert coverage_delta(current=95.0, previous=90.0) == 5.0

    def test_drop_detected(self) -> None:
        assert is_coverage_drop(current=88.0, previous=95.0, drop_threshold_percent=2.0)

    def test_drop_not_detected_for_small_dip(self) -> None:
        assert not is_coverage_drop(current=94.5, previous=95.0, drop_threshold_percent=2.0)


class TestPerformanceEngine:
    def test_within_threshold_lower_is_better(self) -> None:
        assert is_within_threshold(100.0, threshold=200.0)

    def test_outside_threshold_lower_is_better(self) -> None:
        assert not is_within_threshold(300.0, threshold=200.0)

    def test_within_threshold_higher_is_better(self) -> None:
        assert is_within_threshold(500.0, threshold=200.0, higher_is_better=True)

    def test_regression_detected(self) -> None:
        assert is_performance_regression(baseline=100.0, measured=150.0, tolerance_percent=10.0)

    def test_regression_not_detected_within_tolerance(self) -> None:
        assert not is_performance_regression(baseline=100.0, measured=105.0, tolerance_percent=10.0)

    def test_regression_zero_baseline(self) -> None:
        assert is_performance_regression(baseline=0.0, measured=10.0, tolerance_percent=10.0)


class TestBenchmarkEngine:
    def test_percent_change_positive(self) -> None:
        assert percent_change(baseline=100.0, measured=120.0) == pytest.approx(20.0)

    def test_percent_change_zero_baseline_zero_measured(self) -> None:
        assert percent_change(baseline=0.0, measured=0.0) == 0.0

    def test_percent_change_zero_baseline_positive_measured(self) -> None:
        assert percent_change(baseline=0.0, measured=5.0) == 100.0

    def test_regression_higher_is_better(self) -> None:
        assert is_benchmark_regression(
            baseline=1000.0, measured=800.0, tolerance_percent=10.0, higher_is_better=True
        )

    def test_not_regression_higher_is_better_within_tolerance(self) -> None:
        assert not is_benchmark_regression(
            baseline=1000.0, measured=950.0, tolerance_percent=10.0, higher_is_better=True
        )

    def test_regression_lower_is_better(self) -> None:
        assert is_benchmark_regression(
            baseline=100.0, measured=150.0, tolerance_percent=10.0, higher_is_better=False
        )


class TestSecurityEngine:
    def test_passed(self) -> None:
        assert classify_security_result(0) == CheckResultStatus.PASSED

    def test_warning(self) -> None:
        assert classify_security_result(2) == CheckResultStatus.WARNING

    def test_failed(self) -> None:
        assert classify_security_result(10) == CheckResultStatus.FAILED


class TestChaosEngine:
    def test_recovery_within_target(self) -> None:
        assert is_recovery_within_target(30.0, target_seconds=60.0)

    def test_recovery_outside_target(self) -> None:
        assert not is_recovery_within_target(90.0, target_seconds=60.0)

    def test_classify_passed(self) -> None:
        assert classify_chaos_result(30.0, target_seconds=60.0) == CheckResultStatus.PASSED

    def test_classify_warning(self) -> None:
        assert classify_chaos_result(90.0, target_seconds=60.0) == CheckResultStatus.WARNING

    def test_classify_failed(self) -> None:
        assert classify_chaos_result(200.0, target_seconds=60.0) == CheckResultStatus.FAILED


class TestSyntheticEngine:
    def test_availability_full(self) -> None:
        assert availability_percentage(successful_checks=10, total_checks=10) == 100.0

    def test_availability_partial(self) -> None:
        assert availability_percentage(successful_checks=8, total_checks=10) == 80.0

    def test_availability_vacuous(self) -> None:
        assert availability_percentage(successful_checks=0, total_checks=0) == 100.0


class TestContractEngine:
    def test_parse_tolerates_v_prefix_and_suffix(self) -> None:
        assert parse_semantic_version("v1.2.3-beta").major == 1

    def test_parse_rejects_malformed(self) -> None:
        with pytest.raises(ValueError, match="not a valid"):
            parse_semantic_version("not-a-version")

    def test_compatible_same_version(self) -> None:
        assert (
            classify_contract_compatibility(provider_version="1.0.0", consumer_version="1.0.0")
            == CheckResultStatus.PASSED
        )

    def test_compatible_newer_minor_provider(self) -> None:
        assert (
            classify_contract_compatibility(provider_version="1.1.0", consumer_version="1.0.0")
            == CheckResultStatus.PASSED
        )

    def test_warning_newer_major_provider(self) -> None:
        assert (
            classify_contract_compatibility(provider_version="2.0.0", consumer_version="1.0.0")
            == CheckResultStatus.WARNING
        )

    def test_failed_older_provider(self) -> None:
        assert (
            classify_contract_compatibility(provider_version="1.0.0", consumer_version="1.1.0")
            == CheckResultStatus.FAILED
        )


class TestAnalyticsEngine:
    def test_pass_rate(self) -> None:
        assert pass_rate(8, 10) == pytest.approx(0.8)

    def test_pass_rate_empty(self) -> None:
        assert pass_rate(0, 0) == 0.0

    def test_failure_rate(self) -> None:
        assert failure_rate(2, 10) == pytest.approx(0.2)

    def test_flaky_rate(self) -> None:
        assert flaky_rate(1, 10) == pytest.approx(0.1)

    def test_quality_score(self) -> None:
        score = quality_score(
            pass_rate_value=0.9, coverage_percentage=90.0, quality_gate_pass_rate=1.0
        )
        assert score == pytest.approx((0.9 + 0.9 + 1.0) / 3)

    def test_is_flaky_true_for_mixed_results(self) -> None:
        assert is_flaky([ResultStatus.PASSED, ResultStatus.FAILED, ResultStatus.PASSED])

    def test_is_flaky_false_for_all_passed(self) -> None:
        assert not is_flaky([ResultStatus.PASSED, ResultStatus.PASSED])

    def test_is_flaky_false_for_all_failed(self) -> None:
        assert not is_flaky([ResultStatus.FAILED, ResultStatus.FAILED])

    def test_is_flaky_false_for_empty(self) -> None:
        assert not is_flaky([])
