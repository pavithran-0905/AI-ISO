"""Developer portal session lifetime checks.

Pure functions only -- the caller already resolved the session's own
``expires_at`` from a repository row.
"""

from __future__ import annotations

from datetime import datetime


def is_session_expired(*, expires_at: datetime, now: datetime) -> bool:
    """Whether a portal session's ``expires_at`` has already passed."""
    return now >= expires_at


__all__ = ["is_session_expired"]
