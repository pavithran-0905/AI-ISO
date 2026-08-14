"""Tests for app.cli.engine: CLI update attempt lifecycle transitions."""

from __future__ import annotations

from app.cli.engine import ALLOWED_TRANSITIONS, TransitionRefusal, validate_transition
from app.models.enums import CliUpdateStatus


class TestValidateTransition:
    def test_pending_to_downloading_is_allowed(self) -> None:
        assert validate_transition(CliUpdateStatus.PENDING, CliUpdateStatus.DOWNLOADING).is_allowed

    def test_downloading_to_applied_is_allowed(self) -> None:
        assert validate_transition(CliUpdateStatus.DOWNLOADING, CliUpdateStatus.APPLIED).is_allowed

    def test_downloading_to_failed_is_allowed(self) -> None:
        assert validate_transition(CliUpdateStatus.DOWNLOADING, CliUpdateStatus.FAILED).is_allowed

    def test_failed_to_pending_retries(self) -> None:
        assert validate_transition(CliUpdateStatus.FAILED, CliUpdateStatus.PENDING).is_allowed

    def test_applied_is_terminal(self) -> None:
        result = validate_transition(CliUpdateStatus.APPLIED, CliUpdateStatus.PENDING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_pending_to_applied_is_invalid(self) -> None:
        result = validate_transition(CliUpdateStatus.PENDING, CliUpdateStatus.APPLIED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_state_has_a_table_entry(self) -> None:
        for status in CliUpdateStatus:
            assert status in ALLOWED_TRANSITIONS
