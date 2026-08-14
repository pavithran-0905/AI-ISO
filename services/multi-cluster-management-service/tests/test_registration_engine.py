"""Tests for app.registration.engine: credential validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.registration.engine import CredentialRefusal, is_credential_expired, validate_credential

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class TestValidateCredential:
    def test_valid_no_expiry(self) -> None:
        result = validate_credential("ref-1", expires_at=None, now=NOW)
        assert result.is_valid

    def test_valid_future_expiry(self) -> None:
        result = validate_credential("ref-1", expires_at=NOW + timedelta(days=30), now=NOW)
        assert result.is_valid

    def test_empty_reference_refused(self) -> None:
        result = validate_credential("", expires_at=None, now=NOW)
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.EMPTY_REFERENCE

    def test_whitespace_only_reference_refused(self) -> None:
        result = validate_credential("   ", expires_at=None, now=NOW)
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.EMPTY_REFERENCE

    def test_already_expired_refused(self) -> None:
        result = validate_credential("ref-1", expires_at=NOW - timedelta(days=1), now=NOW)
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.ALREADY_EXPIRED

    def test_expiring_exactly_now_refused(self) -> None:
        result = validate_credential("ref-1", expires_at=NOW, now=NOW)
        assert not result.is_valid
        assert result.refusal == CredentialRefusal.ALREADY_EXPIRED


class TestIsCredentialExpired:
    def test_no_expiry_never_expired(self) -> None:
        assert not is_credential_expired(None, now=NOW)

    def test_future_expiry_not_expired(self) -> None:
        assert not is_credential_expired(NOW + timedelta(days=1), now=NOW)

    def test_past_expiry_is_expired(self) -> None:
        assert is_credential_expired(NOW - timedelta(days=1), now=NOW)

    def test_expiring_exactly_now_is_expired(self) -> None:
        assert is_credential_expired(NOW, now=NOW)
