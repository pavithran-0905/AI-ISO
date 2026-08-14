"""Tests for app.licenses.engine: license lifecycle transitions and
seat limit validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.licenses.engine import (
    ALLOWED_TRANSITIONS,
    TransitionRefusal,
    has_seat_available,
    is_expired,
    validate_transition,
)
from app.models.enums import LicenseStatus


class TestValidateTransition:
    def test_issued_to_active_is_allowed(self) -> None:
        result = validate_transition(LicenseStatus.ISSUED, LicenseStatus.ACTIVE)
        assert result.is_allowed
        assert result.refusal is None

    def test_active_to_suspended_is_allowed(self) -> None:
        assert validate_transition(LicenseStatus.ACTIVE, LicenseStatus.SUSPENDED).is_allowed

    def test_suspended_to_active_is_allowed(self) -> None:
        assert validate_transition(LicenseStatus.SUSPENDED, LicenseStatus.ACTIVE).is_allowed

    def test_expired_to_active_reactivates(self) -> None:
        assert validate_transition(LicenseStatus.EXPIRED, LicenseStatus.ACTIVE).is_allowed

    def test_revoked_is_terminal(self) -> None:
        result = validate_transition(LicenseStatus.REVOKED, LicenseStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_issued_to_suspended_is_invalid(self) -> None:
        result = validate_transition(LicenseStatus.ISSUED, LicenseStatus.SUSPENDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_coerces_plain_string(self) -> None:
        result = validate_transition("issued", "active")  # type: ignore[arg-type]
        assert result.is_allowed

    def test_every_state_has_a_table_entry(self) -> None:
        for status in LicenseStatus:
            assert status in ALLOWED_TRANSITIONS


class TestIsExpired:
    def test_none_never_expires(self) -> None:
        assert not is_expired(None, now=datetime.now(UTC))

    def test_future_expiry_is_not_expired(self) -> None:
        now = datetime.now(UTC)
        assert not is_expired(now + timedelta(days=1), now=now)

    def test_past_expiry_is_expired(self) -> None:
        now = datetime.now(UTC)
        assert is_expired(now - timedelta(days=1), now=now)

    def test_exact_moment_is_expired(self) -> None:
        now = datetime.now(UTC)
        assert is_expired(now, now=now)


class TestHasSeatAvailable:
    def test_unlimited_seats_always_available(self) -> None:
        assert has_seat_available(seat_limit=None, active_activation_count=1_000_000)

    def test_below_limit_is_available(self) -> None:
        assert has_seat_available(seat_limit=5, active_activation_count=4)

    def test_at_limit_is_not_available(self) -> None:
        assert not has_seat_available(seat_limit=5, active_activation_count=5)

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            has_seat_available(seat_limit=5, active_activation_count=-1)
