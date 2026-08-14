"""Tests for app.packaging.engine: checksum computation and
verification."""

from __future__ import annotations

from app.packaging.engine import compute_checksum, verify_checksum


class TestComputeChecksum:
    def test_is_deterministic(self) -> None:
        assert compute_checksum(b"content") == compute_checksum(b"content")

    def test_differs_for_different_content(self) -> None:
        assert compute_checksum(b"content") != compute_checksum(b"other")

    def test_is_hex_sha256(self) -> None:
        digest = compute_checksum(b"content")
        assert len(digest) == 64
        int(digest, 16)


class TestVerifyChecksum:
    def test_matching_content_verifies(self) -> None:
        checksum = compute_checksum(b"content")
        assert verify_checksum(b"content", expected_checksum=checksum)

    def test_tampered_content_fails(self) -> None:
        checksum = compute_checksum(b"content")
        assert not verify_checksum(b"tampered", expected_checksum=checksum)
