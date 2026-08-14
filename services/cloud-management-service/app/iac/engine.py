"""Infrastructure-as-Code deployment state transitions.

**A deployment only moves between adjacent, explicitly allowed
states.** A plan that never applied cannot be "drifted" -- drift is
only meaningful once something was actually applied to compare against.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import IaCDeploymentStatus

_S = IaCDeploymentStatus

ALLOWED_TRANSITIONS: dict[IaCDeploymentStatus, frozenset[IaCDeploymentStatus]] = {
    _S.PLANNED: frozenset({_S.APPLYING, _S.FAILED}),
    _S.APPLYING: frozenset({_S.APPLIED, _S.FAILED}),
    _S.APPLIED: frozenset({_S.DRIFTED, _S.DESTROYED, _S.FAILED}),
    _S.DRIFTED: frozenset({_S.APPLYING, _S.DESTROYED}),
    _S.FAILED: frozenset({_S.APPLYING, _S.DESTROYED}),
    _S.DESTROYED: frozenset(),
}
"""Every valid next state. ``DESTROYED`` is the one terminal state."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: IaCDeploymentStatus, target: IaCDeploymentStatus
) -> TransitionResult:
    """Whether an IaC deployment may move from *current* to *target*.

    Both arguments are coerced through :class:`IaCDeploymentStatus`
    before use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = IaCDeploymentStatus(current)
    target = IaCDeploymentStatus(target)
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
