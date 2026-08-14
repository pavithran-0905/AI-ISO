"""API key expiry/rotation-due detection and rate-limit admission.

**A rate limit of ``None`` means unlimited, never "zero."** Mirrors the
same discipline ``app.entitlements``-style limit checks use elsewhere
in this platform: a limit that was never configured is not the same
fact as one set to zero.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta


def compute_key_hash(raw_key: str) -> str:
    """The SHA-256 hex digest of a raw API key -- the only form ever
    persisted. The raw key itself is shown to the caller exactly once,
    at issuance, and is not recoverable from this hash."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def is_key_expired(expires_at: datetime | None, *, now: datetime) -> bool:
    """Whether an API key has passed its expiry.

    ``expires_at is None`` means the key never expires.
    """
    return expires_at is not None and expires_at <= now


def is_rotation_due(
    last_rotated_at: datetime | None, *, now: datetime, rotation_interval_days: int
) -> bool:
    """Whether an API key is due for rotation.

    ``last_rotated_at is None`` (never rotated since issuance) is
    always due.

    Raises:
        ValueError: On a non-positive *rotation_interval_days*.
    """
    if rotation_interval_days < 1:
        raise ValueError(
            f"rotation_interval_days must be at least 1; got {rotation_interval_days}."
        )
    if last_rotated_at is None:
        return True
    return now >= last_rotated_at + timedelta(days=rotation_interval_days)


def is_within_rate_limit(
    request_count_in_window: int, *, rate_limit_per_minute: int | None
) -> bool:
    """Whether one more request is still within an API key's
    configured per-minute rate limit.

    ``rate_limit_per_minute is None`` means unlimited -- always within
    limit.

    Raises:
        ValueError: On a negative *request_count_in_window*.
    """
    if request_count_in_window < 0:
        raise ValueError(
            f"request_count_in_window must be non-negative; got {request_count_in_window}."
        )
    if rate_limit_per_minute is None:
        return True
    return request_count_in_window < rate_limit_per_minute


__all__ = ["compute_key_hash", "is_key_expired", "is_rotation_due", "is_within_rate_limit"]
