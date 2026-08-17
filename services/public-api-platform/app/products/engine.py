"""API product governance workflow transitions."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ApiProductStatus

_S = ApiProductStatus

ALLOWED_TRANSITIONS: dict[ApiProductStatus, frozenset[ApiProductStatus]] = {
    _S.DRAFT: frozenset({_S.PENDING_APPROVAL}),
    _S.PENDING_APPROVAL: frozenset({_S.APPROVED, _S.DRAFT}),
    _S.APPROVED: frozenset({_S.DEPRECATED}),
    _S.DEPRECATED: frozenset(),
}
"""``PENDING_APPROVAL -> DRAFT`` is the rejection path: a product review
that fails sends the product back for rework, not into limbo.
``DEPRECATED`` is the one truly terminal state."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: ApiProductStatus, target: ApiProductStatus) -> TransitionResult:
    """Whether an API product may move from *current* to *target*."""
    current = ApiProductStatus(current)
    target = ApiProductStatus(target)
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
