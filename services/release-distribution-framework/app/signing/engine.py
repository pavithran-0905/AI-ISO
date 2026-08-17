"""Checksum computation and verification.

Real, executable hashing -- not a declared seam -- since computing a
checksum over bytes this process already holds is genuine work, unlike
signing (which needs a private key this service never holds; see
``app.services.supply_chain``'s own module docstring for that
boundary).
"""

from __future__ import annotations

import hashlib

from app.models.enums import ChecksumAlgorithm

_HASHERS = {
    ChecksumAlgorithm.SHA256: hashlib.sha256,
    ChecksumAlgorithm.SHA512: hashlib.sha512,
    ChecksumAlgorithm.MD5: hashlib.md5,
}


def compute_checksum(
    data: bytes, *, algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256
) -> str:
    """Compute a hex-encoded checksum of *data* using *algorithm*."""
    hasher = _HASHERS[ChecksumAlgorithm(algorithm)]()
    hasher.update(data)
    return hasher.hexdigest()


def verify_checksum(*, expected: str, actual: str) -> bool:
    """Whether an expected checksum matches an actual one,
    case-insensitively (hex digests are conventionally lowercase but
    some tooling emits uppercase)."""
    return expected.strip().lower() == actual.strip().lower()


__all__ = ["compute_checksum", "verify_checksum"]
