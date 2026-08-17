"""Code playground session staleness."""

from __future__ import annotations

from datetime import datetime, timedelta


def is_playground_session_stale(
    *, last_active_at: datetime, now: datetime, max_age_hours: int
) -> bool:
    """Whether a playground session has been idle past its own
    configured maximum age and should be expired."""
    return now - last_active_at >= timedelta(hours=max_age_hours)


__all__ = ["is_playground_session_stale"]
