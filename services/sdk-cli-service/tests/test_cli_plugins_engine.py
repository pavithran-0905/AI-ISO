"""Tests for app.cli.plugins.engine: CLI plugin lifecycle transitions."""

from __future__ import annotations

from app.cli.plugins.engine import ALLOWED_TRANSITIONS, TransitionRefusal, validate_transition
from app.models.enums import PluginStatus


class TestValidateTransition:
    def test_available_to_installed_is_allowed(self) -> None:
        assert validate_transition(PluginStatus.AVAILABLE, PluginStatus.INSTALLED).is_allowed

    def test_installed_to_deprecated_is_allowed(self) -> None:
        assert validate_transition(PluginStatus.INSTALLED, PluginStatus.DEPRECATED).is_allowed

    def test_installed_to_removed_is_allowed(self) -> None:
        assert validate_transition(PluginStatus.INSTALLED, PluginStatus.REMOVED).is_allowed

    def test_removed_to_available_reinstalls(self) -> None:
        assert validate_transition(PluginStatus.REMOVED, PluginStatus.AVAILABLE).is_allowed

    def test_available_to_removed_is_invalid(self) -> None:
        result = validate_transition(PluginStatus.AVAILABLE, PluginStatus.REMOVED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_state_has_a_table_entry(self) -> None:
        for status in PluginStatus:
            assert status in ALLOWED_TRANSITIONS
