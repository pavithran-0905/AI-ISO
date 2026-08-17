"""The shared job lifecycle for release builds.

One state machine, reused unmodified by ``ReleaseBuildService`` and
the timeout sweep worker -- the same event-free shared-job-engine shape
every prior AI-IOS service in this build (076-079) established.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import BuildStatus

_S = BuildStatus

ALLOWED_TRANSITIONS: dict[BuildStatus, frozenset[BuildStatus]] = {
    _S.PENDING: frozenset({_S.RUNNING}),
    _S.RUNNING: frozenset({_S.SUCCEEDED, _S.FAILED}),
    _S.SUCCEEDED: frozenset(),
    _S.FAILED: frozenset(),
}

TERMINAL_STATUSES = frozenset({_S.SUCCEEDED, _S.FAILED})


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: BuildStatus, target: BuildStatus) -> TransitionResult:
    """Whether a release build may move from *current* to *target*."""
    current = BuildStatus(current)
    target = BuildStatus(target)
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


def is_job_stuck(
    status: BuildStatus, *, started_at: datetime | None, now: datetime, max_age_hours: float
) -> bool:
    """Whether a release build has been ``RUNNING`` past its own
    configured maximum age -- the condition the timeout sweep worker
    looks for."""
    status = BuildStatus(status)
    if status != _S.RUNNING or started_at is None:
        return False
    elapsed_hours = (now - started_at).total_seconds() / 3600
    return elapsed_hours >= max_age_hours


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "TransitionRefusal",
    "TransitionResult",
    "is_job_stuck",
    "validate_transition",
]
