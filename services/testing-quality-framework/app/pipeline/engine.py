"""The shared job lifecycle for test runs and pipeline results.

Reused, unmodified, across both -- one state machine, not two copies
of an identical one, mirroring
``services/upgrade-framework-service``'s own shared job-engine
precedent (Prompt 076).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import TestRunStatus

_S = TestRunStatus

ALLOWED_TRANSITIONS: dict[TestRunStatus, frozenset[TestRunStatus]] = {
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


def validate_transition(current: TestRunStatus, target: TestRunStatus) -> TransitionResult:
    """Whether a job-shaped row may move from *current* to *target*."""
    current = TestRunStatus(current)
    target = TestRunStatus(target)
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
    status: TestRunStatus, *, started_at: datetime | None, now: datetime, max_age_hours: float
) -> bool:
    """Whether a job-shaped row has been ``RUNNING`` past its own
    configured maximum age -- the condition every timeout sweep worker
    in this service looks for."""
    status = TestRunStatus(status)
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
