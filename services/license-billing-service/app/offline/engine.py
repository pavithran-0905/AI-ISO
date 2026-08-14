"""Offline license file validation.

**A license file is validated against its own recorded hash, never
trusted because it merely parses.** A tampered file that still parses
correctly must still fail validation -- the hash comparison is the only
thing standing between "this file looks right" and "this is the exact
file this service issued."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


class OfflineLicenseRefusal:
    HASH_MISMATCH = "hash_mismatch"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class OfflineLicenseValidation:
    is_valid: bool
    refusal: str | None
    detail: str


def compute_file_hash(file_content: bytes) -> str:
    """The SHA-256 hex digest of a license file's content, used both
    to issue and to later validate it."""
    return hashlib.sha256(file_content).hexdigest()


def validate_offline_license(
    file_content: bytes,
    *,
    expected_hash: str,
    is_revoked: bool,
    expires_at: datetime,
    now: datetime,
) -> OfflineLicenseValidation:
    """Whether an offline license file is genuine, unrevoked, and
    unexpired."""
    if compute_file_hash(file_content) != expected_hash:
        return OfflineLicenseValidation(
            is_valid=False,
            refusal=OfflineLicenseRefusal.HASH_MISMATCH,
            detail="This file's content does not match the hash recorded at issuance.",
        )
    if is_revoked:
        return OfflineLicenseValidation(
            is_valid=False,
            refusal=OfflineLicenseRefusal.REVOKED,
            detail="This license has been revoked.",
        )
    if expires_at <= now:
        return OfflineLicenseValidation(
            is_valid=False,
            refusal=OfflineLicenseRefusal.EXPIRED,
            detail=f"This license expired at {expires_at.isoformat()}.",
        )
    return OfflineLicenseValidation(is_valid=True, refusal=None, detail="License file is valid.")


__all__ = [
    "OfflineLicenseRefusal",
    "OfflineLicenseValidation",
    "compute_file_hash",
    "validate_offline_license",
]
