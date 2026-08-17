"""The release lifecycle engine.

Unlike the shared job-status engines elsewhere in this build
(PENDING/RUNNING/SUCCEEDED/FAILED), a release version drives through a
linear packaging pipeline: DRAFT -> VALIDATED -> SIGNED -> PUBLISHED,
with ARCHIVED reachable from PUBLISHED only. There is no "failed"
state for the version itself -- a release build's own failure is
tracked separately on ``ReleaseBuild`` (see ``app.release_build.engine``),
since a version can always be re-built and re-attempted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ReleaseStatus

_S = ReleaseStatus

ALLOWED_TRANSITIONS: dict[ReleaseStatus, frozenset[ReleaseStatus]] = {
    _S.DRAFT: frozenset({_S.VALIDATED}),
    _S.VALIDATED: frozenset({_S.SIGNED}),
    _S.SIGNED: frozenset({_S.PUBLISHED}),
    _S.PUBLISHED: frozenset({_S.ARCHIVED}),
    _S.ARCHIVED: frozenset(),
}

TERMINAL_STATUSES = frozenset({_S.ARCHIVED})


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: ReleaseStatus, target: ReleaseStatus) -> TransitionResult:
    """Whether a release version may move from *current* to
    *target*."""
    current = ReleaseStatus(current)
    target = ReleaseStatus(target)
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


def next_status_toward(current: ReleaseStatus, target: ReleaseStatus) -> ReleaseStatus | None:
    """The single next status on the path from *current* toward
    *target*, or ``None`` if *current* already equals *target* or no
    path exists.

    Used by ``POST /releases/publish`` to walk a DRAFT release all the
    way to PUBLISHED in one operator action, since docs/080 names no
    separate ``POST /releases/validate``/``POST /releases/sign``
    routes of their own.
    """
    current = ReleaseStatus(current)
    target = ReleaseStatus(target)
    if current == target:
        return None
    order = [_S.DRAFT, _S.VALIDATED, _S.SIGNED, _S.PUBLISHED, _S.ARCHIVED]
    if current not in order or target not in order:
        return None
    current_index = order.index(current)
    target_index = order.index(target)
    if target_index <= current_index:
        return None
    return order[current_index + 1]


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "TransitionRefusal",
    "TransitionResult",
    "next_status_toward",
    "validate_transition",
]
