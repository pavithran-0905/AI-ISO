"""Tests for app.sdk.engine: SDK release lifecycle transitions."""

from __future__ import annotations

from app.models.enums import ReleaseStatus
from app.sdk.engine import ALLOWED_TRANSITIONS, TransitionRefusal, validate_transition


class TestValidateTransition:
    def test_draft_to_published_is_allowed(self) -> None:
        assert validate_transition(ReleaseStatus.DRAFT, ReleaseStatus.PUBLISHED).is_allowed

    def test_published_to_deprecated_is_allowed(self) -> None:
        assert validate_transition(ReleaseStatus.PUBLISHED, ReleaseStatus.DEPRECATED).is_allowed

    def test_published_to_yanked_is_allowed(self) -> None:
        assert validate_transition(ReleaseStatus.PUBLISHED, ReleaseStatus.YANKED).is_allowed

    def test_deprecated_to_yanked_is_allowed(self) -> None:
        assert validate_transition(ReleaseStatus.DEPRECATED, ReleaseStatus.YANKED).is_allowed

    def test_yanked_is_terminal(self) -> None:
        result = validate_transition(ReleaseStatus.YANKED, ReleaseStatus.PUBLISHED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_draft_to_deprecated_is_invalid(self) -> None:
        result = validate_transition(ReleaseStatus.DRAFT, ReleaseStatus.DEPRECATED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_coerces_plain_string(self) -> None:
        assert validate_transition("draft", "published").is_allowed  # type: ignore[arg-type]

    def test_every_state_has_a_table_entry(self) -> None:
        for status in ReleaseStatus:
            assert status in ALLOWED_TRANSITIONS
