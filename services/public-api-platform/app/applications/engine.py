"""Developer application lifecycle transitions."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ApplicationStatus

_S = ApplicationStatus

ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    _S.PENDING: frozenset({_S.ACTIVE, _S.REVOKED}),
    _S.ACTIVE: frozenset({_S.SUSPENDED, _S.REVOKED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.REVOKED}),
    _S.REVOKED: frozenset(),
}
"""``REVOKED`` is the one truly terminal state -- a revoked application
is never reinstated; re-registration is a brand new application."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: ApplicationStatus, target: ApplicationStatus) -> TransitionResult:
    """Whether an application may move from *current* to *target*."""
    current = ApplicationStatus(current)
    target = ApplicationStatus(target)
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


__all__ = ["ALLOWED_TRANSITIONS", "TransitionRefusal", "TransitionResult", "validate_transition"]
