"""Tests for app.immutability.engine: retention lock and legal hold transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.immutability.engine import (
    LockRefusal,
    apply_legal_hold,
    apply_retention_lock,
    release_legal_hold,
)
from app.models.enums import ImmutabilityState

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class TestApplyRetentionLock:
    def test_no_existing_lock_accepted(self) -> None:
        result = apply_retention_lock(
            requested_until=NOW + timedelta(days=30), existing_lock_until=None
        )
        assert result.accepted
        assert result.new_lock_until == NOW + timedelta(days=30)
        assert result.new_state is ImmutabilityState.RETENTION_LOCKED

    def test_extending_existing_lock_accepted(self) -> None:
        existing = NOW + timedelta(days=10)
        result = apply_retention_lock(
            requested_until=NOW + timedelta(days=30), existing_lock_until=existing
        )
        assert result.accepted
        assert result.new_lock_until == NOW + timedelta(days=30)

    def test_shortening_existing_lock_refused(self) -> None:
        existing = NOW + timedelta(days=30)
        result = apply_retention_lock(
            requested_until=NOW + timedelta(days=10), existing_lock_until=existing
        )
        assert not result.accepted
        assert result.refusal == LockRefusal.WOULD_SHORTEN_EXISTING_LOCK
        assert result.new_lock_until == existing

    def test_same_date_accepted(self) -> None:
        existing = NOW + timedelta(days=30)
        result = apply_retention_lock(requested_until=existing, existing_lock_until=existing)
        assert result.accepted


class TestApplyLegalHold:
    def test_valid_reason_returns_legal_hold_state(self) -> None:
        result = apply_legal_hold(reason="litigation hold, case #123")
        assert result is ImmutabilityState.LEGAL_HOLD

    def test_empty_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="must state a reason"):
            apply_legal_hold(reason="")

    def test_whitespace_only_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="must state a reason"):
            apply_legal_hold(reason="   ")


class TestReleaseLegalHold:
    def test_no_underlying_lock_returns_none_state(self) -> None:
        result = release_legal_hold(retention_lock_until=None, now=NOW)
        assert result is ImmutabilityState.NONE

    def test_expired_underlying_lock_returns_none_state(self) -> None:
        result = release_legal_hold(retention_lock_until=NOW - timedelta(days=1), now=NOW)
        assert result is ImmutabilityState.NONE

    def test_active_underlying_lock_falls_back_to_locked(self) -> None:
        result = release_legal_hold(retention_lock_until=NOW + timedelta(days=1), now=NOW)
        assert result is ImmutabilityState.RETENTION_LOCKED

    def test_lock_expiring_exactly_now_returns_none_state(self) -> None:
        result = release_legal_hold(retention_lock_until=NOW, now=NOW)
        assert result is ImmutabilityState.NONE
