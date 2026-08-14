"""Tests for app.api_management.engine: key hash computation, expiry,
rotation-due detection, and rate-limit admission."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.api_management.engine import (
    compute_key_hash,
    is_key_expired,
    is_rotation_due,
    is_within_rate_limit,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestComputeKeyHash:
    def test_is_deterministic(self) -> None:
        assert compute_key_hash("secret") == compute_key_hash("secret")

    def test_differs_for_different_keys(self) -> None:
        assert compute_key_hash("secret-a") != compute_key_hash("secret-b")

    def test_is_hex_sha256(self) -> None:
        digest = compute_key_hash("secret")
        assert len(digest) == 64
        int(digest, 16)


class TestIsKeyExpired:
    def test_none_never_expires(self) -> None:
        assert not is_key_expired(None, now=NOW)

    def test_future_expiry_is_not_expired(self) -> None:
        assert not is_key_expired(NOW + timedelta(days=1), now=NOW)

    def test_past_expiry_is_expired(self) -> None:
        assert is_key_expired(NOW - timedelta(days=1), now=NOW)


class TestIsRotationDue:
    def test_never_rotated_is_due(self) -> None:
        assert is_rotation_due(None, now=NOW, rotation_interval_days=90)

    def test_recently_rotated_is_not_due(self) -> None:
        assert not is_rotation_due(NOW - timedelta(days=1), now=NOW, rotation_interval_days=90)

    def test_past_interval_is_due(self) -> None:
        assert is_rotation_due(NOW - timedelta(days=91), now=NOW, rotation_interval_days=90)

    def test_non_positive_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            is_rotation_due(None, now=NOW, rotation_interval_days=0)


class TestIsWithinRateLimit:
    def test_below_limit(self) -> None:
        assert is_within_rate_limit(5, rate_limit_per_minute=10)

    def test_at_limit_is_not_within(self) -> None:
        assert not is_within_rate_limit(10, rate_limit_per_minute=10)

    def test_none_limit_is_unlimited(self) -> None:
        assert is_within_rate_limit(1_000_000, rate_limit_per_minute=None)

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            is_within_rate_limit(-1, rate_limit_per_minute=10)
