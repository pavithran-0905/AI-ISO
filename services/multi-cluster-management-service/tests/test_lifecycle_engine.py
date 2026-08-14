"""Tests for app.lifecycle.engine: cluster lifecycle state transitions."""

from __future__ import annotations

from app.lifecycle.engine import TransitionRefusal, is_terminal, validate_transition
from app.models.enums import ClusterLifecycleState as S


class TestValidateTransition:
    def test_discovered_to_registered_allowed(self) -> None:
        result = validate_transition(S.DISCOVERED, S.REGISTERED)
        assert result.is_allowed

    def test_discovered_to_active_invalid(self) -> None:
        result = validate_transition(S.DISCOVERED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_full_provisioning_chain(self) -> None:
        chain = [
            (S.DISCOVERED, S.REGISTERED),
            (S.REGISTERED, S.VALIDATING),
            (S.VALIDATING, S.VALIDATED),
            (S.VALIDATED, S.PROVISIONING),
            (S.PROVISIONING, S.PROVISIONED),
            (S.PROVISIONED, S.CONFIGURING),
            (S.CONFIGURING, S.ACTIVE),
        ]
        for current, target in chain:
            result = validate_transition(current, target)
            assert result.is_allowed, f"{current} -> {target} should be allowed"

    def test_active_can_reach_every_operational_state(self) -> None:
        for target in (S.UPGRADING, S.SCALING, S.MAINTENANCE, S.SUSPENDED, S.DECOMMISSIONING):
            result = validate_transition(S.ACTIVE, target)
            assert result.is_allowed, f"ACTIVE -> {target} should be allowed"

    def test_operational_states_return_to_active(self) -> None:
        for state in (S.UPGRADING, S.SCALING, S.MAINTENANCE):
            result = validate_transition(state, S.ACTIVE)
            assert result.is_allowed

    def test_suspended_can_resume_or_decommission(self) -> None:
        assert validate_transition(S.SUSPENDED, S.ACTIVE).is_allowed
        assert validate_transition(S.SUSPENDED, S.DECOMMISSIONING).is_allowed

    def test_decommissioned_can_archive(self) -> None:
        assert validate_transition(S.DECOMMISSIONED, S.ARCHIVED).is_allowed

    def test_archived_is_terminal(self) -> None:
        result = validate_transition(S.ARCHIVED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_failed_can_retry_or_decommission(self) -> None:
        assert validate_transition(S.FAILED, S.REGISTERED).is_allowed
        assert validate_transition(S.FAILED, S.DECOMMISSIONING).is_allowed

    def test_failed_cannot_jump_to_active(self) -> None:
        result = validate_transition(S.FAILED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_non_terminal_state_can_reach_failed(self) -> None:
        for state in (
            S.DISCOVERED,
            S.REGISTERED,
            S.VALIDATING,
            S.VALIDATED,
            S.PROVISIONING,
            S.PROVISIONED,
            S.CONFIGURING,
            S.ACTIVE,
            S.UPGRADING,
            S.SCALING,
            S.MAINTENANCE,
            S.SUSPENDED,
            S.DECOMMISSIONING,
        ):
            result = validate_transition(state, S.FAILED)
            assert result.is_allowed, f"{state} -> FAILED should be allowed"


class TestIsTerminal:
    def test_archived_is_terminal(self) -> None:
        assert is_terminal(S.ARCHIVED)

    def test_active_is_not_terminal(self) -> None:
        assert not is_terminal(S.ACTIVE)

    def test_decommissioned_is_not_terminal(self) -> None:
        assert not is_terminal(S.DECOMMISSIONED)
