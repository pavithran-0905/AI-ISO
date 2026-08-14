"""CLI session expiry checking.

A pure, timezone-aware comparison -- kept as its own tiny engine rather
than inlined, so both the session service and the expiry sweep worker
share exactly one definition of "expired."
"""

from __future__ import annotations

from datetime import datetime


def is_session_expired(expires_at: datetime, *, now: datetime) -> bool:
    """Whether a CLI session has passed its own recorded expiry."""
    return now >= expires_at


__all__ = ["is_session_expired"]
