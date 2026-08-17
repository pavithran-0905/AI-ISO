"""Developer account lifecycle transitions.

Unlike most AI-IOS lifecycle engines, ``SUSPENDED`` is not terminal
here -- a suspended developer account can be reinstated once whatever
issue caused the suspension is resolved. Only the exact
``PENDING_VERIFICATION`` state, once left, is never returned to: a
verified developer does not go back to being unverified.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import DeveloperAccountStatus

_S = DeveloperAccountStatus

ALLOWED_TRANSITIONS: dict[DeveloperAccountStatus, frozenset[DeveloperAccountStatus]] = {
    _S.PENDING_VERIFICATION: frozenset({_S.ACTIVE, _S.SUSPENDED}),
    _S.ACTIVE: frozenset({_S.SUSPENDED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE}),
}


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: DeveloperAccountStatus, target: DeveloperAccountStatus
) -> TransitionResult:
    """Whether a developer account may move from *current* to *target*.

    Both arguments are coerced through :class:`DeveloperAccountStatus`
    before use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = DeveloperAccountStatus(current)
    target = DeveloperAccountStatus(target)
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


def is_eligible_for_activation(email_verified_at: datetime | None) -> bool:
    """Whether a developer account has satisfied the one precondition
    for leaving ``PENDING_VERIFICATION``: a verified email address."""
    return email_verified_at is not None


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_eligible_for_activation",
    "validate_transition",
]
