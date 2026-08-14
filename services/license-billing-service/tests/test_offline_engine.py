"""Tests for app.offline.engine: offline license file hash validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.offline.engine import OfflineLicenseRefusal, compute_file_hash, validate_offline_license

_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_CONTENT = b"license-file-content"


class TestComputeFileHash:
    def test_is_deterministic(self) -> None:
        assert compute_file_hash(_CONTENT) == compute_file_hash(_CONTENT)

    def test_differs_for_different_content(self) -> None:
        assert compute_file_hash(_CONTENT) != compute_file_hash(b"other-content")

    def test_is_hex_sha256(self) -> None:
        digest = compute_file_hash(_CONTENT)
        assert len(digest) == 64
        int(digest, 16)  # raises ValueError if not valid hex


class TestValidateOfflineLicense:
    def test_valid_file(self) -> None:
        result = validate_offline_license(
            _CONTENT,
            expected_hash=compute_file_hash(_CONTENT),
            is_revoked=False,
            expires_at=_NOW + timedelta(days=1),
            now=_NOW,
        )
        assert result.is_valid

    def test_tampered_file_fails_hash(self) -> None:
        result = validate_offline_license(
            b"tampered",
            expected_hash=compute_file_hash(_CONTENT),
            is_revoked=False,
            expires_at=_NOW + timedelta(days=1),
            now=_NOW,
        )
        assert not result.is_valid
        assert result.refusal == OfflineLicenseRefusal.HASH_MISMATCH

    def test_revoked_file_fails(self) -> None:
        result = validate_offline_license(
            _CONTENT,
            expected_hash=compute_file_hash(_CONTENT),
            is_revoked=True,
            expires_at=_NOW + timedelta(days=1),
            now=_NOW,
        )
        assert not result.is_valid
        assert result.refusal == OfflineLicenseRefusal.REVOKED

    def test_expired_file_fails(self) -> None:
        result = validate_offline_license(
            _CONTENT,
            expected_hash=compute_file_hash(_CONTENT),
            is_revoked=False,
            expires_at=_NOW - timedelta(days=1),
            now=_NOW,
        )
        assert not result.is_valid
        assert result.refusal == OfflineLicenseRefusal.EXPIRED

    def test_hash_mismatch_takes_priority_over_revoked(self) -> None:
        result = validate_offline_license(
            b"tampered",
            expected_hash=compute_file_hash(_CONTENT),
            is_revoked=True,
            expires_at=_NOW + timedelta(days=1),
            now=_NOW,
        )
        assert result.refusal == OfflineLicenseRefusal.HASH_MISMATCH
