"""Package checksum computation and integrity verification.

**A package is verified against its own recorded checksum, never
trusted because it merely downloaded successfully.** A corrupted or
tampered artifact that still transferred completely must still fail
verification -- the checksum comparison is the only thing standing
between "this download finished" and "this is the exact artifact this
service published."
"""

from __future__ import annotations

import hashlib


def compute_checksum(content: bytes) -> str:
    """The SHA-256 hex digest of a package artifact's content."""
    return hashlib.sha256(content).hexdigest()


def verify_checksum(content: bytes, *, expected_checksum: str) -> bool:
    """Whether *content* matches its own recorded checksum."""
    return compute_checksum(content) == expected_checksum


__all__ = ["compute_checksum", "verify_checksum"]
