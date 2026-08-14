"""Maintenance window lifecycle transitions, overlap detection, and
schedule-due checks.

**Two maintenance windows overlapping is a real conflict this engine
can detect before either is approved** -- rolling maintenance and
emergency maintenance both depend on the platform never entering two
uncoordinated maintenance operations at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import MaintenanceStatus

_S = MaintenanceStatus

ALLOWED_TRANSITIONS: dict[MaintenanceStatus, frozenset[MaintenanceStatus]] = {
    _S.SCHEDULED: frozenset({_S.APPROVED, _S.CANCELLED}),
    _S.APPROVED: frozenset({_S.IN_PROGRESS, _S.CANCELLED}),
    _S.IN_PROGRESS: frozenset({_S.COMPLETED}),
    _S.COMPLETED: frozenset(),
    _S.CANCELLED: frozenset(),
}
"""Every valid next state. ``COMPLETED`` and ``CANCELLED`` are both
terminal."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: MaintenanceStatus, target: MaintenanceStatus) -> TransitionResult:
    """Whether a maintenance window may move from *current* to
    *target*.

    Both arguments are coerced through :class:`MaintenanceStatus`
    before use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = MaintenanceStatus(current)
    target = MaintenanceStatus(target)
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


def windows_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Whether two ``[start, end]`` maintenance windows overlap at all.

    Raises:
        ValueError: If either window's end precedes its own start.
    """
    if a_end < a_start or b_end < b_start:
        raise ValueError("A window's end must not precede its own start.")
    return a_start <= b_end and b_start <= a_end


def is_due_to_start(status: MaintenanceStatus, *, starts_at: datetime, now: datetime) -> bool:
    """Whether an approved window's start time has arrived."""
    return MaintenanceStatus(status) == MaintenanceStatus.APPROVED and now >= starts_at


def is_due_to_complete(status: MaintenanceStatus, *, ends_at: datetime, now: datetime) -> bool:
    """Whether an in-progress window's end time has passed."""
    return MaintenanceStatus(status) == MaintenanceStatus.IN_PROGRESS and now >= ends_at


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_due_to_complete",
    "is_due_to_start",
    "validate_transition",
    "windows_overlap",
]
