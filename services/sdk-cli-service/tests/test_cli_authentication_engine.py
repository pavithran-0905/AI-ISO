"""Tests for app.cli.authentication.engine: CLI session expiry
checking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.cli.authentication.engine import is_session_expired

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestIsSessionExpired:
    def test_future_expiry_is_not_expired(self) -> None:
        assert not is_session_expired(NOW + timedelta(minutes=1), now=NOW)

    def test_past_expiry_is_expired(self) -> None:
        assert is_session_expired(NOW - timedelta(minutes=1), now=NOW)

    def test_exact_moment_is_expired(self) -> None:
        assert is_session_expired(NOW, now=NOW)
