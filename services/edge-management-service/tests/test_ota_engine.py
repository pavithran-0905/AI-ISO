"""Tests for app.ota.engine: OTA update plan validation and rollback
decisions."""

from __future__ import annotations

from app.ota.engine import UpdateRefusal, should_roll_back, validate_update_plan


class TestValidateUpdatePlan:
    def test_forward_update_within_skew_is_valid(self) -> None:
        result = validate_update_plan(0, 2, max_skew=2)
        assert result.is_valid
        assert result.skew == 2

    def test_same_version_refused(self) -> None:
        result = validate_update_plan(1, 1, max_skew=2)
        assert not result.is_valid
        assert result.refusal == UpdateRefusal.SAME_VERSION

    def test_downgrade_refused(self) -> None:
        result = validate_update_plan(2, 1, max_skew=2)
        assert not result.is_valid
        assert result.refusal == UpdateRefusal.DOWNGRADE

    def test_skew_exceeded_refused(self) -> None:
        result = validate_update_plan(0, 5, max_skew=2)
        assert not result.is_valid
        assert result.refusal == UpdateRefusal.SKEW_EXCEEDED

    def test_skew_exactly_at_max_is_valid(self) -> None:
        result = validate_update_plan(0, 3, max_skew=3)
        assert result.is_valid


class TestShouldRollBack:
    def test_explicit_failure_triggers_rollback(self) -> None:
        assert should_roll_back(verification_passed=False)

    def test_explicit_success_does_not_roll_back(self) -> None:
        assert not should_roll_back(verification_passed=True)

    def test_unverified_does_not_roll_back(self) -> None:
        assert not should_roll_back(verification_passed=None)
