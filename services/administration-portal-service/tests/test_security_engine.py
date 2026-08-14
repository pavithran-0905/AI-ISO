"""Tests for app.security.engine: password policy validation, IP
allowlist matching, and session expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.security.engine import is_ip_allowed, is_session_expired, validate_password_policy

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestValidatePasswordPolicy:
    def test_valid_password(self) -> None:
        result = validate_password_policy(
            "Abcdef1!",
            min_length=8,
            require_upper=True,
            require_lower=True,
            require_digit=True,
            require_symbol=True,
        )
        assert result.is_valid
        assert result.violations == ()

    def test_too_short(self) -> None:
        result = validate_password_policy(
            "Ab1!",
            min_length=8,
            require_upper=True,
            require_lower=True,
            require_digit=True,
            require_symbol=True,
        )
        assert not result.is_valid
        assert any("8 characters" in v for v in result.violations)

    def test_missing_every_class_is_named(self) -> None:
        result = validate_password_policy(
            "aaaaaaaa",
            min_length=8,
            require_upper=True,
            require_lower=True,
            require_digit=True,
            require_symbol=True,
        )
        assert not result.is_valid
        assert len(result.violations) == 3  # upper, digit, symbol (lower is satisfied)

    def test_relaxed_policy_only_checks_length(self) -> None:
        result = validate_password_policy(
            "aaaaaaaa",
            min_length=8,
            require_upper=False,
            require_lower=False,
            require_digit=False,
            require_symbol=False,
        )
        assert result.is_valid

    def test_non_positive_min_length_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            validate_password_policy(
                "x",
                min_length=0,
                require_upper=False,
                require_lower=False,
                require_digit=False,
                require_symbol=False,
            )


class TestIsIpAllowed:
    def test_empty_allowlist_allows_everything(self) -> None:
        assert is_ip_allowed("1.2.3.4", allowed_cidrs=[])

    def test_matching_cidr_is_allowed(self) -> None:
        assert is_ip_allowed("10.0.0.5", allowed_cidrs=["10.0.0.0/24"])

    def test_non_matching_cidr_is_refused(self) -> None:
        assert not is_ip_allowed("192.168.1.1", allowed_cidrs=["10.0.0.0/24"])

    def test_matches_any_of_multiple_cidrs(self) -> None:
        assert is_ip_allowed("192.168.1.1", allowed_cidrs=["10.0.0.0/24", "192.168.1.0/24"])

    def test_invalid_ip_raises(self) -> None:
        with pytest.raises(ValueError):
            is_ip_allowed("not-an-ip", allowed_cidrs=["10.0.0.0/24"])


class TestIsSessionExpired:
    def test_within_max_age_is_not_expired(self) -> None:
        assert not is_session_expired(
            started_at=NOW - timedelta(minutes=10), max_age_minutes=60, now=NOW
        )

    def test_past_max_age_is_expired(self) -> None:
        assert is_session_expired(
            started_at=NOW - timedelta(minutes=90), max_age_minutes=60, now=NOW
        )

    def test_exact_boundary_is_expired(self) -> None:
        assert is_session_expired(
            started_at=NOW - timedelta(minutes=60), max_age_minutes=60, now=NOW
        )

    def test_non_positive_max_age_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            is_session_expired(started_at=NOW, max_age_minutes=0, now=NOW)
