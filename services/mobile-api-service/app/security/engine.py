"""Device integrity scoring, certificate fingerprint validation, and
replay-attack detection.

Pure functions only -- every signal (jailbreak/root flags, a
certificate fingerprint, a request's own timestamp) is passed in by the
caller, which already resolved it from the device's own request or
from a repository row.
"""

from __future__ import annotations

from datetime import datetime

MAX_INTEGRITY_SCORE = 100
_JAILBREAK_PENALTY = 60
_ROOT_PENALTY = 60
_INVALID_CERTIFICATE_PENALTY = 40
DEFAULT_INTEGRITY_THRESHOLD = 50

_SHA256_HEX_LENGTH = 64


def compute_integrity_risk_score(
    *, is_jailbroken: bool, is_rooted: bool, certificate_valid: bool = True
) -> int:
    """A device's integrity risk score: ``0`` is pristine,
    :data:`MAX_INTEGRITY_SCORE` is maximally compromised."""
    score = 0
    if is_jailbroken:
        score += _JAILBREAK_PENALTY
    if is_rooted:
        score += _ROOT_PENALTY
    if not certificate_valid:
        score += _INVALID_CERTIFICATE_PENALTY
    return min(score, MAX_INTEGRITY_SCORE)


def is_device_integrity_acceptable(
    score: int, *, threshold: int = DEFAULT_INTEGRITY_THRESHOLD
) -> bool:
    """Whether a device's integrity score stays under the risk
    *threshold* it is still trusted to authenticate."""
    return score < threshold


def is_valid_certificate_fingerprint(fingerprint: str) -> bool:
    """Whether *fingerprint* is a well-formed SHA-256 hex digest (64
    lowercase hex characters) -- the format certificate pinning
    compares against, not a live chain-of-trust check."""
    if len(fingerprint) != _SHA256_HEX_LENGTH:
        return False
    return all(char in "0123456789abcdef" for char in fingerprint)


def is_replay_attack(
    *, request_timestamp: datetime, now: datetime, max_skew_seconds: int, nonce_already_seen: bool
) -> bool:
    """Whether a request should be rejected as a replay: either its own
    nonce was already used, or its timestamp falls outside the
    tolerated clock-skew window."""
    if nonce_already_seen:
        return True
    skew = abs((now - request_timestamp).total_seconds())
    return skew > max_skew_seconds


__all__ = [
    "DEFAULT_INTEGRITY_THRESHOLD",
    "MAX_INTEGRITY_SCORE",
    "compute_integrity_risk_score",
    "is_device_integrity_acceptable",
    "is_replay_attack",
    "is_valid_certificate_fingerprint",
]
