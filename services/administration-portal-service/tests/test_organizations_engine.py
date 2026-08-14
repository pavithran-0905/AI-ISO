"""Tests for app.organizations.engine: organization lifecycle
transitions."""

from __future__ import annotations

from app.models.enums import OrganizationStatus
from app.organizations.engine import ALLOWED_TRANSITIONS, TransitionRefusal, validate_transition


class TestValidateTransition:
    def test_active_to_suspended_is_allowed(self) -> None:
        assert validate_transition(
            OrganizationStatus.ACTIVE, OrganizationStatus.SUSPENDED
        ).is_allowed

    def test_suspended_to_active_is_allowed(self) -> None:
        assert validate_transition(
            OrganizationStatus.SUSPENDED, OrganizationStatus.ACTIVE
        ).is_allowed

    def test_active_to_archived_is_allowed(self) -> None:
        assert validate_transition(
            OrganizationStatus.ACTIVE, OrganizationStatus.ARCHIVED
        ).is_allowed

    def test_archived_is_terminal(self) -> None:
        result = validate_transition(OrganizationStatus.ARCHIVED, OrganizationStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_same_state_is_invalid(self) -> None:
        result = validate_transition(OrganizationStatus.ACTIVE, OrganizationStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_coerces_plain_string(self) -> None:
        assert validate_transition("active", "suspended").is_allowed  # type: ignore[arg-type]

    def test_every_state_has_a_table_entry(self) -> None:
        for status in OrganizationStatus:
            assert status in ALLOWED_TRANSITIONS
