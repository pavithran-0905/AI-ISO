"""Encryption key lifecycle: rotation scheduling.

**Rotation is due-date arithmetic, never the encryption itself.** The
actual AES-256-GCM sealing lives in the storage layer this service calls
out to; what belongs here is the one decision that is pure and worth
testing in isolation -- whether a key has aged past its rotation policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class KeyRotationCheck:
    is_due: bool
    key_age_days: float
    rotation_days: int


def check_rotation_due(
    key_created_at: datetime, *, rotation_days: int, now: datetime
) -> KeyRotationCheck:
    """Whether an encryption key has aged past its rotation policy.

    Raises:
        ValueError: On a non-positive ``rotation_days``, which could
            never be satisfied and would mark every key perpetually due.
    """
    if rotation_days < 1:
        raise ValueError(f"rotation_days must be at least 1; got {rotation_days}.")
    age = now - key_created_at
    age_days = age.total_seconds() / 86_400.0
    return KeyRotationCheck(
        is_due=age >= timedelta(days=rotation_days),
        key_age_days=age_days,
        rotation_days=rotation_days,
    )


__all__ = ["KeyRotationCheck", "check_rotation_due"]
