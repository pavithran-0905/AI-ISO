"""Tests for app.catalog.engine: service catalog approval workflow."""

from __future__ import annotations

from app.catalog.engine import TransitionRefusal, is_provisionable, validate_transition
from app.models.enums import CatalogItemStatus as S


class TestValidateTransition:
    def test_draft_to_pending_approval_allowed(self) -> None:
        assert validate_transition(S.DRAFT, S.PENDING_APPROVAL).is_allowed

    def test_pending_approval_can_approve_or_reject(self) -> None:
        assert validate_transition(S.PENDING_APPROVAL, S.APPROVED).is_allowed
        assert validate_transition(S.PENDING_APPROVAL, S.REJECTED).is_allowed

    def test_approved_can_deprecate(self) -> None:
        assert validate_transition(S.APPROVED, S.DEPRECATED).is_allowed

    def test_rejected_can_be_revised(self) -> None:
        assert validate_transition(S.REJECTED, S.DRAFT).is_allowed

    def test_deprecated_is_terminal(self) -> None:
        result = validate_transition(S.DEPRECATED, S.DRAFT)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_draft_cannot_jump_to_approved(self) -> None:
        result = validate_transition(S.DRAFT, S.APPROVED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION


class TestIsProvisionable:
    def test_approved_is_provisionable(self) -> None:
        assert is_provisionable(S.APPROVED)

    def test_draft_is_not_provisionable(self) -> None:
        assert not is_provisionable(S.DRAFT)
