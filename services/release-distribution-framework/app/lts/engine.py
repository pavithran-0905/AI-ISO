"""LTS support-window expiration checking."""

from __future__ import annotations

from datetime import datetime


def is_support_expiring_soon(
    *, support_ends_at: datetime, now: datetime, warning_days: int
) -> bool:
    """Whether an LTS line's own support window falls within the
    configured warning period, counting from *now*."""
    days_remaining = (support_ends_at - now).total_seconds() / 86400
    return 0 <= days_remaining <= warning_days


def is_support_expired(*, support_ends_at: datetime, now: datetime) -> bool:
    """Whether an LTS line's own support window has already ended."""
    return now >= support_ends_at


__all__ = ["is_support_expired", "is_support_expiring_soon"]
