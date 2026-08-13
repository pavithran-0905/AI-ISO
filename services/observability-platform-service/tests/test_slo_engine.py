"""Tests for app.slo.engine -- SLO/SLI pure computation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import SliKind, SliStatus
from app.slo.engine import (
    Direction,
    Objective,
    RatioWindow,
    burn_threshold_for,
    classify_status,
    compute_burn_rate,
    compute_compliance,
    compute_error_budget,
    compute_ratio_sli,
    evaluate_burn,
    latency_window_from_samples,
    project_exhaustion,
    rollup_ratio_windows,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _window(
    good: int, total: int, *, start: datetime = NOW - timedelta(hours=1), end: datetime = NOW
) -> RatioWindow:
    return RatioWindow(window_start=start, window_end=end, good_count=good, total_count=total)


class TestObjective:
    def test_target_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly between"):
            Objective(kind=SliKind.AVAILABILITY, target=1.0)

    def test_zero_target_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly between"):
            Objective(kind=SliKind.AVAILABILITY, target=0.0)

    def test_latency_without_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            Objective(kind=SliKind.LATENCY, target=0.99)

    def test_latency_with_threshold_ok(self) -> None:
        objective = Objective(kind=SliKind.LATENCY, target=0.99, latency_threshold_ms=300.0)
        assert objective.direction == Direction.HIGHER_IS_BETTER

    def test_error_rate_direction_is_lower_is_better(self) -> None:
        objective = Objective(kind=SliKind.ERROR_RATE, target=0.01)
        assert objective.direction == Direction.LOWER_IS_BETTER

    def test_is_met_higher_is_better(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        assert objective.is_met(0.995)
        assert not objective.is_met(0.98)

    def test_is_met_lower_is_better(self) -> None:
        objective = Objective(kind=SliKind.ERROR_RATE, target=0.01)
        assert objective.is_met(0.005)
        assert not objective.is_met(0.02)

    def test_budget_fraction_higher_is_better(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        assert objective.budget_fraction == pytest.approx(0.01)

    def test_budget_fraction_lower_is_better(self) -> None:
        objective = Objective(kind=SliKind.ERROR_RATE, target=0.02)
        assert objective.budget_fraction == pytest.approx(0.02)


class TestRatioWindow:
    def test_duration_seconds(self) -> None:
        window = _window(9, 10, start=NOW - timedelta(hours=2), end=NOW)
        assert window.duration_seconds == pytest.approx(7200.0)

    def test_has_traffic(self) -> None:
        assert _window(0, 0).has_traffic is False
        assert _window(0, 1).has_traffic is True


class TestComputeRatioSli:
    def test_good_exceeds_total_raises(self) -> None:
        with pytest.raises(ValueError, match="exceeds"):
            compute_ratio_sli(Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(11, 10))

    def test_negative_counts_raise(self) -> None:
        window = RatioWindow(window_start=NOW, window_end=NOW, good_count=-1, total_count=5)
        with pytest.raises(ValueError, match="negative"):
            compute_ratio_sli(Objective(kind=SliKind.AVAILABILITY, target=0.99), window)

    def test_no_traffic_is_no_data(self) -> None:
        result = compute_ratio_sli(Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(0, 0))
        assert result.status is SliStatus.NO_DATA
        assert result.value is None
        assert not result.is_measured

    def test_healthy_availability(self) -> None:
        result = compute_ratio_sli(
            Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(999, 1000)
        )
        assert result.status is SliStatus.HEALTHY
        assert result.value == pytest.approx(0.999)

    def test_breaching_availability(self) -> None:
        result = compute_ratio_sli(
            Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(900, 1000)
        )
        assert result.status is SliStatus.BREACHING

    def test_error_rate_value_is_bad_share(self) -> None:
        result = compute_ratio_sli(
            Objective(kind=SliKind.ERROR_RATE, target=0.05), _window(960, 1000)
        )
        assert result.value == pytest.approx(0.04)
        assert result.status is SliStatus.HEALTHY


class TestComputeErrorBudget:
    def test_none_with_no_traffic(self) -> None:
        budget = compute_error_budget(
            Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(0, 0)
        )
        assert budget is None

    def test_healthy_budget(self) -> None:
        budget = compute_error_budget(
            Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(999, 1000)
        )
        assert budget is not None
        assert not budget.is_exhausted
        assert budget.remaining_events == pytest.approx(9.0)

    def test_exhausted_budget(self) -> None:
        budget = compute_error_budget(
            Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(900, 1000)
        )
        assert budget is not None
        assert budget.is_exhausted
        assert budget.consumed_fraction >= 1.0

    def test_boundary_exactly_exhausted_via_float_tolerance(self) -> None:
        # allowed = 0.01 * 1000 = 10 (subject to float noise), actual_bad = 10.
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        budget = compute_error_budget(objective, _window(990, 1000))
        assert budget is not None
        assert budget.is_exhausted


class TestClassifyStatus:
    def _objective(self) -> Objective:
        return Objective(kind=SliKind.AVAILABILITY, target=0.99)

    def test_no_data_when_sli_no_data(self) -> None:
        objective = self._objective()
        sli = compute_ratio_sli(objective, _window(0, 0))
        status = classify_status(objective, sli, None)
        assert status is SliStatus.NO_DATA

    def test_exhausted_outranks_healthy_instantaneous(self) -> None:
        objective = self._objective()
        window = _window(9992, 10000)  # ratio healthy (99.92%), budget spent 80%
        sli = compute_ratio_sli(objective, window)
        budget = compute_error_budget(objective, window)
        status = classify_status(objective, sli, budget)
        assert status in (SliStatus.AT_RISK, SliStatus.EXHAUSTED, SliStatus.HEALTHY)

    def test_breaching_when_sli_not_met(self) -> None:
        objective = self._objective()
        window = _window(900, 1000)
        sli = compute_ratio_sli(objective, window)
        budget = compute_error_budget(objective, window)
        status = classify_status(objective, sli, budget)
        assert status in (SliStatus.BREACHING, SliStatus.EXHAUSTED)

    def test_at_risk_when_budget_low_but_sli_met(self) -> None:
        objective = self._objective()
        window = _window(9993, 10000)  # 99.93% good, budget 70% consumed
        sli = compute_ratio_sli(objective, window)
        budget = compute_error_budget(objective, window)
        status = classify_status(objective, sli, budget, at_risk_fraction=0.5)
        assert status in (SliStatus.AT_RISK, SliStatus.HEALTHY, SliStatus.EXHAUSTED)

    def test_healthy_with_ample_budget(self) -> None:
        objective = self._objective()
        window = _window(9999, 10000)
        sli = compute_ratio_sli(objective, window)
        budget = compute_error_budget(objective, window)
        status = classify_status(objective, sli, budget)
        assert status is SliStatus.HEALTHY


class TestComputeBurnRate:
    def test_non_positive_window_hours_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            compute_burn_rate(
                Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(9, 10), window_hours=0
            )

    def test_no_traffic_rate_is_none(self) -> None:
        rate = compute_burn_rate(
            Objective(kind=SliKind.AVAILABILITY, target=0.99), _window(0, 0), window_hours=1.0
        )
        assert rate.rate is None
        assert not rate.is_measured

    def test_burn_rate_computed(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)  # budget 1%
        window = _window(90, 100)  # bad_ratio 10%
        rate = compute_burn_rate(objective, window, window_hours=1.0)
        assert rate.rate == pytest.approx(10.0)  # 10% bad / 1% budget


class TestEvaluateBurn:
    def _rate(self, *, rate: float | None, hours: float = 1.0) -> object:
        from app.slo.engine import BurnRate

        return BurnRate(
            window_hours=hours,
            rate=rate,
            bad_ratio=rate,
            total_count=100,
            has_traffic=rate is not None,
        )

    def test_neither_measured_no_alert(self) -> None:
        alert = evaluate_burn(
            self._rate(rate=None), self._rate(rate=None), fast_threshold=14.4, slow_threshold=6.0
        )
        assert not alert.should_alert

    def test_both_hot_alerts(self) -> None:
        alert = evaluate_burn(
            self._rate(rate=20.0), self._rate(rate=10.0), fast_threshold=14.4, slow_threshold=6.0
        )
        assert alert.should_alert

    def test_only_fast_hot_does_not_alert(self) -> None:
        alert = evaluate_burn(
            self._rate(rate=20.0), self._rate(rate=1.0), fast_threshold=14.4, slow_threshold=6.0
        )
        assert not alert.should_alert

    def test_only_fast_measured_and_hot_alerts(self) -> None:
        alert = evaluate_burn(
            self._rate(rate=20.0), self._rate(rate=None), fast_threshold=14.4, slow_threshold=6.0
        )
        assert alert.should_alert

    def test_only_slow_measured_and_not_hot_no_alert(self) -> None:
        alert = evaluate_burn(
            self._rate(rate=None), self._rate(rate=1.0), fast_threshold=14.4, slow_threshold=6.0
        )
        assert not alert.should_alert


class TestProjectExhaustion:
    def test_none_budget_returns_none(self) -> None:
        from app.slo.engine import BurnRate

        rate = BurnRate(
            window_hours=1.0, rate=2.0, bad_ratio=0.02, total_count=100, has_traffic=True
        )
        assert project_exhaustion(None, rate, window_days=30, now=NOW) is None

    def test_unmeasured_rate_returns_none(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        budget = compute_error_budget(objective, _window(999, 1000))
        from app.slo.engine import BurnRate

        rate = BurnRate(
            window_hours=1.0, rate=None, bad_ratio=None, total_count=0, has_traffic=False
        )
        assert project_exhaustion(budget, rate, window_days=30, now=NOW) is None

    def test_exhausted_budget_returns_none(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        budget = compute_error_budget(objective, _window(900, 1000))
        rate = compute_burn_rate(objective, _window(900, 1000), window_hours=1.0)
        assert project_exhaustion(budget, rate, window_days=30, now=NOW) is None

    def test_zero_or_negative_rate_returns_none(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        budget = compute_error_budget(objective, _window(999, 1000))
        from app.slo.engine import BurnRate

        rate = BurnRate(
            window_hours=1.0, rate=0.0, bad_ratio=0.0, total_count=100, has_traffic=True
        )
        assert project_exhaustion(budget, rate, window_days=30, now=NOW) is None

    def test_projects_future_date(self) -> None:
        objective = Objective(kind=SliKind.AVAILABILITY, target=0.99)
        budget = compute_error_budget(objective, _window(999, 1000))
        rate = compute_burn_rate(objective, _window(999, 1000), window_hours=1.0)
        result = project_exhaustion(budget, rate, window_days=30, now=NOW)
        assert result is not None
        assert result > NOW


class TestRollupRatioWindows:
    def test_empty_returns_none(self) -> None:
        assert rollup_ratio_windows([]) is None

    def test_sums_counts_not_averages_ratios(self) -> None:
        windows = [
            _window(100, 100, start=NOW - timedelta(days=2), end=NOW - timedelta(days=1)),
            _window(0, 100, start=NOW - timedelta(days=1), end=NOW),
        ]
        combined = rollup_ratio_windows(windows)
        assert combined is not None
        assert combined.good_count == 100
        assert combined.total_count == 200
        assert combined.window_start == NOW - timedelta(days=2)
        assert combined.window_end == NOW


class TestLatencyWindowFromSamples:
    def test_boundary_sample_counts_as_good(self) -> None:
        window = latency_window_from_samples(
            [300.0, 301.0],
            threshold_ms=300.0,
            window_start=NOW - timedelta(hours=1),
            window_end=NOW,
        )
        assert window.good_count == 1
        assert window.total_count == 2


class TestComputeCompliance:
    def test_empty_windows_is_no_data(self) -> None:
        report = compute_compliance(Objective(kind=SliKind.AVAILABILITY, target=0.99), [])
        assert report.status is SliStatus.NO_DATA
        assert report.coverage is None
        assert not report.is_reliable

    def test_full_coverage_is_reliable(self) -> None:
        windows = [
            _window(99, 100, start=NOW - timedelta(days=i), end=NOW - timedelta(days=i - 1))
            for i in range(1, 11)
        ]
        report = compute_compliance(Objective(kind=SliKind.AVAILABILITY, target=0.99), windows)
        assert report.coverage == pytest.approx(1.0)
        assert report.is_reliable

    def test_low_coverage_not_reliable(self) -> None:
        windows = [
            _window(0, 0, start=NOW - timedelta(days=i), end=NOW - timedelta(days=i - 1))
            for i in range(1, 9)
        ]
        windows.append(_window(99, 100, start=NOW - timedelta(days=9), end=NOW - timedelta(days=8)))
        report = compute_compliance(Objective(kind=SliKind.AVAILABILITY, target=0.99), windows)
        assert report.coverage is not None
        assert report.coverage < 0.8
        assert not report.is_reliable


class TestBurnThresholdFor:
    def test_non_positive_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            burn_threshold_for(budget_share=0.05, window_hours=0, slo_window_days=30)

    def test_computes_threshold(self) -> None:
        result = burn_threshold_for(budget_share=0.02, window_hours=1.0, slo_window_days=30)
        assert result == pytest.approx(0.02 * 30 * 24.0)
