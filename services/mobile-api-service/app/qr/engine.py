"""QR-code onboarding token generation and verification.

A QR token is a one-time, opaque, cryptographically random bearer
credential: possessing it is sufficient to complete the one enrollment
action it was minted for, so it must be unguessable
(:func:`secrets.token_urlsafe`, never a counter or a hash of
predictable input) and single-use (checked by the caller against
whatever repository row tracks whether it was already redeemed -- not
this module's concern).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

_TOKEN_BYTES = 32


def generate_qr_token() -> str:
    """A fresh, unguessable one-time QR enrollment token."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def compute_qr_expiry(*, issued_at: datetime, ttl_minutes: int) -> datetime:
    """The instant a QR token minted at *issued_at* stops being
    redeemable."""
    return issued_at + timedelta(minutes=ttl_minutes)


def is_qr_token_expired(*, issued_at: datetime, ttl_minutes: int, now: datetime) -> bool:
    """Whether a QR token minted at *issued_at* has passed its own TTL."""
    return now >= compute_qr_expiry(issued_at=issued_at, ttl_minutes=ttl_minutes)


__all__ = ["compute_qr_expiry", "generate_qr_token", "is_qr_token_expired"]
