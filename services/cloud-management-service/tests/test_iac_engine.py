"""Tests for app.iac.engine: IaC deployment state transitions."""

from __future__ import annotations

from app.iac.engine import TransitionRefusal, validate_transition
from app.models.enums import IaCDeploymentStatus as S


class TestValidateTransition:
    def test_planned_to_applying_allowed(self) -> None:
        assert validate_transition(S.PLANNED, S.APPLYING).is_allowed

    def test_applying_to_applied_allowed(self) -> None:
        assert validate_transition(S.APPLYING, S.APPLIED).is_allowed

    def test_applied_can_drift_or_destroy(self) -> None:
        assert validate_transition(S.APPLIED, S.DRIFTED).is_allowed
        assert validate_transition(S.APPLIED, S.DESTROYED).is_allowed

    def test_drifted_can_reapply_or_destroy(self) -> None:
        assert validate_transition(S.DRIFTED, S.APPLYING).is_allowed
        assert validate_transition(S.DRIFTED, S.DESTROYED).is_allowed

    def test_failed_can_retry_or_destroy(self) -> None:
        assert validate_transition(S.FAILED, S.APPLYING).is_allowed
        assert validate_transition(S.FAILED, S.DESTROYED).is_allowed

    def test_destroyed_is_terminal(self) -> None:
        result = validate_transition(S.DESTROYED, S.APPLYING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_planned_cannot_jump_to_applied(self) -> None:
        result = validate_transition(S.PLANNED, S.APPLIED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION
