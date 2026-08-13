"""Tests for app.encryption.engine: key rotation due-date arithmetic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.encryption.engine import check_rotation_due

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class TestCheckRotationDue:
    def test_freshly_created_key_not_due(self) -> None:
        result = check_rotation_due(NOW, rotation_days=90, now=NOW)
        assert not result.is_due
        assert result.key_age_days == 0

    def test_key_within_policy_not_due(self) -> None:
        created = NOW - timedelta(days=30)
        result = check_rotation_due(created, rotation_days=90, now=NOW)
        assert not result.is_due

    def test_key_exactly_at_policy_is_due(self) -> None:
        created = NOW - timedelta(days=90)
        result = check_rotation_due(created, rotation_days=90, now=NOW)
        assert result.is_due

    def test_key_past_policy_is_due(self) -> None:
        created = NOW - timedelta(days=200)
        result = check_rotation_due(created, rotation_days=90, now=NOW)
        assert result.is_due
        assert result.key_age_days == pytest.approx(200.0)

    def test_zero_rotation_days_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            check_rotation_due(NOW, rotation_days=0, now=NOW)

    def test_negative_rotation_days_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            check_rotation_due(NOW, rotation_days=-1, now=NOW)
