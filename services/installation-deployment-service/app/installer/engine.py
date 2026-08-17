"""Installation session lifecycle.

A session is PENDING until it starts running, then moves to exactly one
of two terminal states. Unlike a portal draft/publish cycle, nothing
here is ever revived -- a fresh installation attempt (recovery, repair,
or a plain retry) is always a *new* session row, never a reopening of
an old one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import InstallationSessionStatus

_S = InstallationSessionStatus

ALLOWED_TRANSITIONS: dict[InstallationSessionStatus, frozenset[InstallationSessionStatus]] = {
    _S.PENDING: frozenset({_S.RUNNING}),
    _S.RUNNING: frozenset({_S.SUCCEEDED, _S.FAILED}),
    _S.SUCCEEDED: frozenset(),
    _S.FAILED: frozenset(),
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
    current: InstallationSessionStatus, target: InstallationSessionStatus
) -> TransitionResult:
    """Whether an installation session may move from *current* to *target*."""
    current = InstallationSessionStatus(current)
    target = InstallationSessionStatus(target)
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
