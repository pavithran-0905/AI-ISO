"""The shared job lifecycle for benchmark runs.

One state machine, reused unmodified by ``BenchmarkRunService`` and
the timeout sweep worker -- the same event-free shared-job-engine shape
``services/testing-quality-framework`` (Prompt 077) and
``services/upgrade-framework-service`` (Prompt 076) established.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import BenchmarkRunStatus

_S = BenchmarkRunStatus

ALLOWED_TRANSITIONS: dict[BenchmarkRunStatus, frozenset[BenchmarkRunStatus]] = {
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


def validate_transition(
    current: BenchmarkRunStatus, target: BenchmarkRunStatus
) -> TransitionResult:
    """Whether a benchmark run may move from *current* to *target*."""
    current = BenchmarkRunStatus(current)
    target = BenchmarkRunStatus(target)
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
    status: BenchmarkRunStatus, *, started_at: datetime | None, now: datetime, max_age_hours: float
) -> bool:
    """Whether a benchmark run has been ``RUNNING`` past its own
    configured maximum age -- the condition the timeout sweep worker
    looks for."""
    status = BenchmarkRunStatus(status)
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
