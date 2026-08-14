"""Tests for app.registration.engine: enrollment credential validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.registration.engine import CredentialRefusal, is_credential_expired, validate_credential


class TestValidateCredential:
    def test_valid_credential_with_no_expiry(self) -> None:
        result = validate_credential("token-abc", expires_at=None, now=datetime.now(UTC))
        assert result.is_valid

    def test_valid_credential_with_future_expiry(self) -> None:
        now = datetime.now(UTC)
        result = validate_credential("token-abc", expires_at=now + timedelta(hours=1), now=now)
        assert result.is_valid

    def test_empty_reference_refused(self) -> None:
        result = validate_credential("   ", expires_at=None, now=datetime.now(UTC))
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.EMPTY_REFERENCE

    def test_already_expired_refused(self) -> None:
        now = datetime.now(UTC)
        result = validate_credential("token-abc", expires_at=now - timedelta(hours=1), now=now)
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.ALREADY_EXPIRED

    def test_expiring_exactly_now_is_expired(self) -> None:
        now = datetime.now(UTC)
        result = validate_credential("token-abc", expires_at=now, now=now)
        assert not result.is_valid


class TestIsCredentialExpired:
    def test_no_expiry_never_expires(self) -> None:
        assert not is_credential_expired(None, now=datetime.now(UTC))

    def test_future_expiry_not_expired(self) -> None:
        now = datetime.now(UTC)
        assert not is_credential_expired(now + timedelta(hours=1), now=now)

    def test_past_expiry_is_expired(self) -> None:
        now = datetime.now(UTC)
        assert is_credential_expired(now - timedelta(hours=1), now=now)
