"""Tests for app.configuration.engine: configuration rollback validation."""

from __future__ import annotations

from app.configuration.engine import RollbackRefusal, validate_rollback


class TestValidateRollback:
    def test_known_earlier_version_is_valid(self) -> None:
        result = validate_rollback(1, current_version=3, known_versions=frozenset({1, 2, 3}))
        assert result.is_valid

    def test_already_active_version_refused(self) -> None:
        result = validate_rollback(3, current_version=3, known_versions=frozenset({1, 2, 3}))
        assert not result.is_valid
        assert result.refusal == RollbackRefusal.ALREADY_ACTIVE

    def test_unknown_version_refused(self) -> None:
        result = validate_rollback(9, current_version=3, known_versions=frozenset({1, 2, 3}))
        assert not result.is_valid
        assert result.refusal == RollbackRefusal.NO_SUCH_VERSION
