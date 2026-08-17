"""Community post lifecycle and reputation scoring."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import CommunityPostStatus

_S = CommunityPostStatus

ALLOWED_TRANSITIONS: dict[CommunityPostStatus, frozenset[CommunityPostStatus]] = {
    _S.OPEN: frozenset({_S.ANSWERED, _S.CLOSED}),
    _S.ANSWERED: frozenset({_S.CLOSED, _S.OPEN}),
    _S.CLOSED: frozenset({_S.OPEN}),
}
"""Nothing here is truly terminal -- a closed thread can always be
reopened, and an answered question can be reopened if the accepted
answer turns out not to resolve it."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: CommunityPostStatus, target: CommunityPostStatus
) -> TransitionResult:
    """Whether a community post may move from *current* to *target*."""
    current = CommunityPostStatus(current)
    target = CommunityPostStatus(target)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        allowed_names = ", ".join(sorted(state.value for state in allowed))
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.INVALID_TRANSITION,
            detail=(
                f"{current.value} cannot transition to {target.value}; "
                f"allowed next states are: {allowed_names or 'none'}."
            ),
        )
    return TransitionResult(
        is_allowed=True, refusal=None, detail=f"{current.value} -> {target.value} is allowed."
    )


def compute_reputation_delta(*, upvotes: int, is_accepted_answer: bool) -> int:
    """A simple, deterministic reputation contribution: one point per
    upvote, plus a fixed bonus for an accepted answer -- the same shape
    every major Q&A community uses, kept intentionally simple since
    this is not the point this build is meant to differentiate on."""
    accepted_bonus = 15 if is_accepted_answer else 0
    return upvotes + accepted_bonus


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "compute_reputation_delta",
    "validate_transition",
]
