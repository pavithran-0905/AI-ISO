"""Shared credential lifecycle for API keys, personal access tokens,
application credentials, and OAuth client secrets -- one state machine,
since all four are "a secret that can be rotated, revoked, or expire"
with identical semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import CredentialStatus

_S = CredentialStatus

ALLOWED_TRANSITIONS: dict[CredentialStatus, frozenset[CredentialStatus]] = {
    _S.ACTIVE: frozenset({_S.ROTATED, _S.REVOKED, _S.EXPIRED}),
    _S.ROTATED: frozenset({_S.REVOKED}),
    _S.EXPIRED: frozenset(),
    _S.REVOKED: frozenset(),
}
"""``EXPIRED`` and ``REVOKED`` are both terminal -- an expired or
revoked credential is never silently reactivated; issuing a new one is
always a fresh row."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: CredentialStatus, target: CredentialStatus) -> TransitionResult:
    """Whether a credential may move from *current* to *target*."""
    current = CredentialStatus(current)
    target = CredentialStatus(target)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if not allowed:
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.TERMINAL_STATE,
            detail=f"{current.value} is a terminal state; no further transition is possible.",
        )
    if target not in allowed:
        allowed_names = ", ".join(sorted(state.value for state in allowed))
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.INVALID_TRANSITION,
            detail=(
                f"{current.value} cannot transition to {target.value}; "
                f"allowed next states are: {allowed_names}."
            ),
        )
    return TransitionResult(
        is_allowed=True, refusal=None, detail=f"{current.value} -> {target.value} is allowed."
    )


def is_expired(*, expires_at: datetime, now: datetime) -> bool:
    """Whether a credential's own ``expires_at`` has already passed."""
    return now >= expires_at


def is_expiring_soon(*, expires_at: datetime, now: datetime, warning_days: int) -> bool:
    """Whether a still-active credential enters its own expiry warning
    window -- the point at which "Credential Expiring" should be
    notified."""
    if is_expired(expires_at=expires_at, now=now):
        return False
    return now >= expires_at - timedelta(days=warning_days)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_expired",
    "is_expiring_soon",
    "validate_transition",
]
