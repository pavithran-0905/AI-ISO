"""Tests for app.upgrades.engine: version skew validation and rollback decisions."""

from __future__ import annotations

from app.upgrades.engine import UpgradeRefusal, should_roll_back, validate_upgrade_plan


class TestValidateUpgradePlan:
    def test_valid_forward_step(self) -> None:
        result = validate_upgrade_plan(5, 6, max_skew=2)
        assert result.is_valid
        assert result.skew == 1

    def test_same_version_refused(self) -> None:
        result = validate_upgrade_plan(5, 5, max_skew=2)
        assert not result.is_valid
        assert result.refusal == UpgradeRefusal.SAME_VERSION

    def test_downgrade_refused(self) -> None:
        result = validate_upgrade_plan(5, 3, max_skew=2)
        assert not result.is_valid
        assert result.refusal == UpgradeRefusal.DOWNGRADE
        assert result.skew == -2

    def test_skew_exceeded_refused(self) -> None:
        result = validate_upgrade_plan(5, 9, max_skew=2)
        assert not result.is_valid
        assert result.refusal == UpgradeRefusal.SKEW_EXCEEDED

    def test_skew_exactly_at_max_allowed(self) -> None:
        result = validate_upgrade_plan(5, 7, max_skew=2)
        assert result.is_valid


class TestShouldRollBack:
    def test_explicit_post_validation_failure_triggers_rollback(self) -> None:
        assert should_roll_back(pre_validation_passed=True, post_validation_passed=False)

    def test_post_validation_never_run_does_not_trigger_rollback(self) -> None:
        assert not should_roll_back(pre_validation_passed=True, post_validation_passed=None)

    def test_post_validation_passed_does_not_trigger_rollback(self) -> None:
        assert not should_roll_back(pre_validation_passed=True, post_validation_passed=True)

    def test_pre_validation_failure_alone_does_not_trigger_rollback(self) -> None:
        assert not should_roll_back(pre_validation_passed=False, post_validation_passed=None)
