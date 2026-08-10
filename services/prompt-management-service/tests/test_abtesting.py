"""Tests for :mod:`app.abtesting.statistics`.

Pure module. The expected values here are textbook constants, not
observations of the implementation -- if the arithmetic ever drifts,
these fail.
"""

from __future__ import annotations

import pytest

from app.abtesting.statistics import (
    MIN_SAMPLES_PER_ARM,
    ArmResult,
    assign_arm,
    evaluate_experiment,
    normal_cdf,
    two_proportion_z_test,
    two_sided_p_value,
)

# ---------------------------------------------------------------------------
# normal_cdf / p-values -- against published values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (0.0, 0.5),
        (1.0, 0.841345),
        (1.96, 0.975002),
        (-1.96, 0.024998),
        (2.576, 0.995002),
        (-3.0, 0.001350),
    ],
)
def test_normal_cdf_matches_published_values(z: float, expected: float) -> None:
    assert normal_cdf(z) == pytest.approx(expected, abs=1e-6)


def test_normal_cdf_is_symmetric() -> None:
    assert normal_cdf(1.5) + normal_cdf(-1.5) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    ("z", "expected"),
    [(1.96, 0.05), (2.576, 0.01), (0.0, 1.0), (3.291, 0.001)],
)
def test_two_sided_p_value_matches_published_values(z: float, expected: float) -> None:
    assert two_sided_p_value(z) == pytest.approx(expected, abs=1e-3)


def test_two_sided_p_value_ignores_sign() -> None:
    """Two-sided means direction does not change the p-value."""
    assert two_sided_p_value(2.0) == pytest.approx(two_sided_p_value(-2.0))


# ---------------------------------------------------------------------------
# ArmResult
# ---------------------------------------------------------------------------


def test_arm_rate() -> None:
    assert ArmResult(executions=200, successes=50).rate == 0.25


def test_arm_rate_of_an_empty_arm_is_zero_not_a_crash() -> None:
    assert ArmResult(executions=0, successes=0).rate == 0.0


# ---------------------------------------------------------------------------
# two_proportion_z_test
# ---------------------------------------------------------------------------


def test_worked_example_matches_hand_computation() -> None:
    """Control 100/1000 = 10%, variant 150/1000 = 15%.

    pooled = 250/2000 = 0.125
    se     = sqrt(0.125 * 0.875 * (1/1000 + 1/1000)) = 0.0147902
    z      = (0.15 - 0.10) / 0.0147902 = 3.3806
    """
    z, p = two_proportion_z_test(ArmResult(1000, 100), ArmResult(1000, 150))
    assert z == pytest.approx(3.3806, abs=1e-3)
    assert p == pytest.approx(0.000723, abs=1e-5)


def test_z_is_negative_when_the_variant_is_worse() -> None:
    z, _ = two_proportion_z_test(ArmResult(1000, 150), ArmResult(1000, 100))
    assert z < 0


def test_identical_arms_give_zero_z_and_p_of_one() -> None:
    z, p = two_proportion_z_test(ArmResult(500, 250), ArmResult(500, 250))
    assert z == pytest.approx(0.0)
    assert p == pytest.approx(1.0)


def test_all_success_everywhere_does_not_divide_by_zero() -> None:
    """Pooled variance is zero -- genuinely no signal, not an error."""
    assert two_proportion_z_test(ArmResult(50, 50), ArmResult(50, 50)) == (0.0, 1.0)


def test_all_failure_everywhere_does_not_divide_by_zero() -> None:
    assert two_proportion_z_test(ArmResult(50, 0), ArmResult(50, 0)) == (0.0, 1.0)


@pytest.mark.parametrize(
    ("control", "variant"),
    [
        (ArmResult(1, 1), ArmResult(50, 25)),
        (ArmResult(50, 25), ArmResult(1, 0)),
        (ArmResult(0, 0), ArmResult(0, 0)),
    ],
)
def test_below_the_arithmetic_floor_returns_no_signal(
    control: ArmResult, variant: ArmResult
) -> None:
    """A proportion needs at least two trials to have a variance."""
    assert two_proportion_z_test(control, variant) == (0.0, 1.0)


def test_min_samples_per_arm_constant() -> None:
    assert MIN_SAMPLES_PER_ARM == 2


# ---------------------------------------------------------------------------
# evaluate_experiment -- the sample-horizon guard
# ---------------------------------------------------------------------------


def test_refuses_significance_before_the_control_arm_fills() -> None:
    result = evaluate_experiment(ArmResult(10, 1), ArmResult(500, 400), minimum_samples_per_arm=100)
    assert result.significant is False
    assert "control arm has 10" in result.reason


def test_refuses_significance_before_the_variant_arm_fills() -> None:
    result = evaluate_experiment(ArmResult(500, 100), ArmResult(10, 9), minimum_samples_per_arm=100)
    assert result.significant is False
    assert "variant arm has 10" in result.reason


def test_undecided_still_reports_the_observed_rates() -> None:
    """An undecided verdict is not a blank -- the rates so far are real."""
    result = evaluate_experiment(ArmResult(10, 5), ArmResult(10, 8), minimum_samples_per_arm=100)
    assert result.control_rate == 0.5
    assert result.variant_rate == 0.8
    assert result.difference == pytest.approx(0.3)
    assert result.p_value == 1.0


def test_significant_when_the_gap_is_large_and_both_arms_are_full() -> None:
    result = evaluate_experiment(
        ArmResult(1000, 100), ArmResult(1000, 150), minimum_samples_per_arm=100
    )
    assert result.significant is True
    assert result.variant_wins is True
    assert "below the 0.05 threshold" in result.reason
    assert "variant arm performed better" in result.reason


def test_not_significant_when_the_gap_is_small() -> None:
    result = evaluate_experiment(
        ArmResult(1000, 500), ArmResult(1000, 505), minimum_samples_per_arm=100
    )
    assert result.significant is False
    assert "does not clear" in result.reason


def test_a_significant_regression_is_not_a_winner() -> None:
    """The variant did significantly WORSE. Promoting it would ship a
    measured regression, so ``variant_wins`` must be False even though
    the result is real."""
    result = evaluate_experiment(
        ArmResult(1000, 150), ArmResult(1000, 100), minimum_samples_per_arm=100
    )
    assert result.significant is True
    assert result.variant_wins is False
    assert result.difference < 0
    assert "control arm performed better" in result.reason


def test_a_stricter_significance_level_is_harder_to_clear() -> None:
    borderline_control = ArmResult(1000, 500)
    borderline_variant = ArmResult(1000, 545)
    lenient = evaluate_experiment(
        borderline_control, borderline_variant, minimum_samples_per_arm=100, significance_level=0.05
    )
    strict = evaluate_experiment(
        borderline_control,
        borderline_variant,
        minimum_samples_per_arm=100,
        significance_level=0.001,
    )
    assert lenient.significant is True
    assert strict.significant is False


def test_exactly_at_the_sample_horizon_is_evaluated() -> None:
    """The horizon is a minimum, not an exclusive bound."""
    result = evaluate_experiment(
        ArmResult(100, 10), ArmResult(100, 60), minimum_samples_per_arm=100
    )
    assert "required" not in result.reason
    assert result.significant is True


# ---------------------------------------------------------------------------
# assign_arm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("weight", "roll", "expected"),
    [
        (0.5, 0.1, True),
        (0.5, 0.9, False),
        (0.0, 0.0, False),
        (1.0, 0.999, True),
        (0.3, 0.3, False),
        (0.3, 0.29, True),
    ],
)
def test_assign_arm(weight: float, roll: float, expected: bool) -> None:
    assert assign_arm(weight, roll) is expected


def test_zero_weight_never_routes_to_the_variant() -> None:
    assert not any(assign_arm(0.0, roll / 100) for roll in range(100))


def test_full_weight_always_routes_to_the_variant() -> None:
    assert all(assign_arm(1.0, roll / 100) for roll in range(100))


@pytest.mark.parametrize("weight", [-0.1, 1.1, 2.0])
def test_assign_arm_refuses_an_out_of_range_weight(weight: float) -> None:
    with pytest.raises(ValueError, match=r"within \[0, 1\]"):
        assign_arm(weight, 0.5)
