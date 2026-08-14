"""Cloud resource lifecycle transitions and staleness detection.

**A resource only moves between adjacent, explicitly allowed states.**
Skipping straight from ``DISCOVERED`` to ``ACTIVE`` would treat a
resource this service has never provisioned or imported as fully
operational.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import CloudResourceLifecycleState

_S = CloudResourceLifecycleState

ALLOWED_TRANSITIONS: dict[CloudResourceLifecycleState, frozenset[CloudResourceLifecycleState]] = {
    _S.DISCOVERED: frozenset({_S.PROVISIONING, _S.IMPORTED, _S.ARCHIVED, _S.FAILED}),
    _S.PROVISIONING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.IMPORTED: frozenset({_S.ACTIVE, _S.ARCHIVED, _S.FAILED}),
    _S.ACTIVE: frozenset(
        {_S.UPDATING, _S.SCALING, _S.SUSPENDED, _S.STOPPED, _S.DELETING, _S.FAILED}
    ),
    _S.UPDATING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.SCALING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.DELETING, _S.FAILED}),
    _S.STOPPED: frozenset({_S.ACTIVE, _S.DELETING, _S.FAILED}),
    _S.DELETING: frozenset({_S.DELETED, _S.FAILED}),
    _S.DELETED: frozenset({_S.ARCHIVED}),
    _S.ARCHIVED: frozenset(),
    _S.FAILED: frozenset({_S.PROVISIONING, _S.DELETING}),
}
"""Every valid next state. ``ARCHIVED`` has none -- it is the one truly
terminal state; ``FAILED`` can still retry (back to ``PROVISIONING``) or
be cleaned up (``DELETING``)."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: CloudResourceLifecycleState, target: CloudResourceLifecycleState
) -> TransitionResult:
    """Whether a resource may move from *current* to *target*.

    Both arguments are coerced through
    :class:`CloudResourceLifecycleState` before use: *current* in
    particular is often read straight from an ORM attribute, which --
    when the row was freshly materialized rather than found live in the
    session's identity map -- carries a plain ``str`` rather than the
    enum instance, since the column is declared as plain ``String`` with
    no Enum type decorator. The coercion is a no-op for an
    already-genuine enum instance.
    """
    current = CloudResourceLifecycleState(current)
    target = CloudResourceLifecycleState(target)
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


def is_terminal(state: CloudResourceLifecycleState) -> bool:
    return not ALLOWED_TRANSITIONS.get(state, frozenset())


def is_stale(last_synced_at: datetime | None, *, now: datetime, threshold_minutes: int) -> bool:
    """Whether a resource has gone too long without a discovery sync.

    ``last_synced_at is None`` (never synced at all) is stale by
    definition -- there is no evidence of it ever having been observed.
    """
    if last_synced_at is None:
        return True
    return now - last_synced_at > timedelta(minutes=threshold_minutes)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_stale",
    "is_terminal",
    "validate_transition",
]
