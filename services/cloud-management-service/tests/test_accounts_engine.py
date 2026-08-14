"""Tests for app.accounts.engine: credential validation and health
classification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.accounts.engine import (
    CredentialRefusal,
    classify_account_health,
    is_account_stale,
    is_credential_expired,
    validate_credential,
)
from app.models.enums import AccountHealthStatus


class TestValidateCredential:
    def test_valid_credential_with_no_expiry(self) -> None:
        result = validate_credential("ref", expires_at=None, now=datetime.now(UTC))
        assert result.is_valid

    def test_empty_reference_refused(self) -> None:
        result = validate_credential("   ", expires_at=None, now=datetime.now(UTC))
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.EMPTY_REFERENCE

    def test_already_expired_refused(self) -> None:
        now = datetime.now(UTC)
        result = validate_credential("ref", expires_at=now - timedelta(hours=1), now=now)
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.ALREADY_EXPIRED


class TestIsCredentialExpired:
    def test_no_expiry_never_expires(self) -> None:
        assert not is_credential_expired(None, now=datetime.now(UTC))

    def test_past_expiry_is_expired(self) -> None:
        now = datetime.now(UTC)
        assert is_credential_expired(now - timedelta(hours=1), now=now)


class TestIsAccountStale:
    def test_never_validated_is_stale(self) -> None:
        assert is_account_stale(None, now=datetime.now(UTC), threshold_minutes=60)

    def test_recently_validated_is_not_stale(self) -> None:
        now = datetime.now(UTC)
        assert not is_account_stale(now - timedelta(minutes=5), now=now, threshold_minutes=60)

    def test_old_validation_is_stale(self) -> None:
        now = datetime.now(UTC)
        assert is_account_stale(now - timedelta(minutes=90), now=now, threshold_minutes=60)


class TestClassifyAccountHealth:
    def test_invalid_is_unhealthy_regardless_of_staleness(self) -> None:
        assert (
            classify_account_health(is_valid=False, is_stale=False) == AccountHealthStatus.UNHEALTHY
        )
        assert (
            classify_account_health(is_valid=False, is_stale=True) == AccountHealthStatus.UNHEALTHY
        )

    def test_valid_and_stale_is_degraded(self) -> None:
        assert classify_account_health(is_valid=True, is_stale=True) == AccountHealthStatus.DEGRADED

    def test_valid_and_fresh_is_healthy(self) -> None:
        assert classify_account_health(is_valid=True, is_stale=False) == AccountHealthStatus.HEALTHY
