"""OAuth2/PKCE verification and token lifetime checks.

Pure functions only -- every signal (a code verifier, a token's own
``expires_at``, a client's allowed grant types) is passed in by the
caller, which already resolved it from the request or a repository
row.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime


def compute_pkce_challenge(code_verifier: str) -> str:
    """The S256 PKCE code challenge for *code_verifier*: the base64url
    (no padding) encoding of its own SHA-256 digest -- per RFC 7636."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_pkce(*, code_verifier: str, code_challenge: str) -> bool:
    """Whether *code_verifier* actually produces *code_challenge*.

    Uses a constant-time comparison: PKCE exists specifically to defend
    an authorization code exchange, so the comparison itself must not
    leak timing information about how much of the challenge matched.
    """
    expected = compute_pkce_challenge(code_verifier)
    return hmac.compare_digest(expected, code_challenge)


def is_token_expired(*, expires_at: datetime, now: datetime) -> bool:
    """Whether an OAuth token's ``expires_at`` has already passed."""
    return now >= expires_at


def is_grant_type_allowed(grant_type: str, allowed_grant_types: list[str]) -> bool:
    """Whether *grant_type* is one of a client's own registered grant
    types."""
    return grant_type in allowed_grant_types


__all__ = [
    "compute_pkce_challenge",
    "is_grant_type_allowed",
    "is_token_expired",
    "verify_pkce",
]
