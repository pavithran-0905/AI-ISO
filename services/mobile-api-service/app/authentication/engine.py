"""Mobile session lifetime and offline-authentication windows.

Pure functions only -- no repository or session access. Every input is
a plain value the caller already has in hand, so these are trivially
hand-verifiable and trivially unit-testable without any database.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def is_session_expired(*, expires_at: datetime, now: datetime) -> bool:
    """Whether a session's ``expires_at`` has already passed."""
    return now >= expires_at


def is_session_expiring_soon(*, expires_at: datetime, now: datetime, warning_minutes: int) -> bool:
    """Whether a still-active session enters its own expiry warning
    window -- the point at which "Session Expiring" should be notified,
    once, before the session actually lapses."""
    if is_session_expired(expires_at=expires_at, now=now):
        return False
    return now >= expires_at - timedelta(minutes=warning_minutes)


def is_offline_authentication_allowed(
    *, last_seen_at: datetime | None, now: datetime, max_offline_hours: int
) -> bool:
    """Whether a device may authenticate offline against its own
    last-known-good online state.

    A device that has never been seen online has no online state to
    trust offline, so it is never eligible.
    """
    if last_seen_at is None:
        return False
    return now - last_seen_at <= timedelta(hours=max_offline_hours)


__all__ = [
    "is_offline_authentication_allowed",
    "is_session_expired",
    "is_session_expiring_soon",
]
