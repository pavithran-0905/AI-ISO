"""Certificate expiration checking."""

from __future__ import annotations

from datetime import datetime


def is_expiring_soon(*, expires_at: datetime, now: datetime, warning_days: int) -> bool:
    """Whether a certificate's own expiration falls within the
    configured warning window, counting from *now*."""
    days_remaining = (expires_at - now).total_seconds() / 86400
    return 0 <= days_remaining <= warning_days


def is_expired(*, expires_at: datetime, now: datetime) -> bool:
    """Whether a certificate has already expired."""
    return now >= expires_at


__all__ = ["is_expired", "is_expiring_soon"]
