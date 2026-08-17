"""GraphQL query sanity checks and webhook test signature/outcome
logic.

Pure functions only -- no network I/O. Actually delivering a webhook
test call is the caller's job (a real HTTP request); this module only
decides what the delivered outcome *means* and what a valid signature
looks like.
"""

from __future__ import annotations

import hashlib
import hmac

from app.models.enums import WebhookTestStatus

_SUCCESS_STATUS_LOWER = 200
_SUCCESS_STATUS_UPPER = 300


def compute_webhook_signature(*, payload_bytes: bytes, secret: str) -> str:
    """The HMAC-SHA256 signature a webhook receiver would compute over
    the raw request body -- the same construction
    ``services/webhook-service`` (Prompt 057) signs deliveries with."""
    return hmac.new(secret.encode("ascii"), payload_bytes, hashlib.sha256).hexdigest()


def verify_webhook_signature(*, payload_bytes: bytes, secret: str, signature: str) -> bool:
    """Whether *signature* actually matches *payload_bytes* signed with
    *secret*, compared in constant time."""
    expected = compute_webhook_signature(payload_bytes=payload_bytes, secret=secret)
    return hmac.compare_digest(expected, signature)


def classify_webhook_response(status_code: int) -> WebhookTestStatus:
    """Classify a webhook test's own HTTP response status code into a
    ``WebhookTestStatus`` -- any ``2xx`` is a success, everything else
    is a failure, matching typical webhook-delivery semantics."""
    if _SUCCESS_STATUS_LOWER <= status_code < _SUCCESS_STATUS_UPPER:
        return WebhookTestStatus.SUCCEEDED
    return WebhookTestStatus.FAILED


def is_well_formed_graphql_query(query_text: str) -> bool:
    """A minimal structural sanity check: a GraphQL document must open
    a selection set. This is deliberately not a full GraphQL parser --
    that belongs to whatever GraphQL server actually executes the
    query; this only screens obviously-empty or malformed input before
    it is ever saved."""
    stripped = query_text.strip()
    return bool(stripped) and "{" in stripped and "}" in stripped


__all__ = [
    "classify_webhook_response",
    "compute_webhook_signature",
    "is_well_formed_graphql_query",
    "verify_webhook_signature",
]
