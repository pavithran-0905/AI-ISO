"""End-of-life schedule checking."""

from __future__ import annotations

from datetime import datetime


def is_eol_approaching(*, eol_date: datetime, now: datetime, warning_days: int) -> bool:
    """Whether a release's own end-of-life date falls within the
    configured warning period, counting from *now*."""
    days_remaining = (eol_date - now).total_seconds() / 86400
    return 0 <= days_remaining <= warning_days


def is_past_eol(*, eol_date: datetime, now: datetime) -> bool:
    """Whether a release's own end-of-life date has already passed."""
    return now >= eol_date


__all__ = ["is_eol_approaching", "is_past_eol"]
