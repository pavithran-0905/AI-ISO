"""Device lifecycle transitions and staleness detection.

**A device only moves between adjacent, explicitly allowed states.**
Skipping straight from ``DISCOVERED`` to ``ACTIVE`` would treat a device
this service has never provisioned or configured as fully operational.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import DeviceLifecycleState

_S = DeviceLifecycleState

ALLOWED_TRANSITIONS: dict[DeviceLifecycleState, frozenset[DeviceLifecycleState]] = {
    _S.DISCOVERED: frozenset({_S.REGISTERED, _S.FAILED}),
    _S.REGISTERED: frozenset({_S.PROVISIONING, _S.FAILED}),
    _S.PROVISIONING: frozenset({_S.PROVISIONED, _S.FAILED}),
    _S.PROVISIONED: frozenset({_S.CONFIGURING, _S.FAILED}),
    _S.CONFIGURING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.ACTIVE: frozenset({_S.MAINTENANCE, _S.SUSPENDED, _S.REPLACING, _S.RETIRING, _S.FAILED}),
    _S.MAINTENANCE: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.RETIRING, _S.FAILED}),
    _S.REPLACING: frozenset({_S.RETIRING, _S.FAILED}),
    _S.RETIRING: frozenset({_S.SECURE_WIPING, _S.RETIRED, _S.FAILED}),
    _S.SECURE_WIPING: frozenset({_S.RETIRED, _S.FAILED}),
    _S.RETIRED: frozenset(),
    _S.FAILED: frozenset({_S.REGISTERED, _S.RETIRING}),
}
"""Every valid next state. ``RETIRED`` has none -- it is the one truly
terminal state; ``FAILED`` can still retry (back to ``REGISTERED``) or be
retired outright."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: DeviceLifecycleState, target: DeviceLifecycleState
) -> TransitionResult:
    """Whether a device may move from *current* to *target*.

    Both arguments are coerced through :class:`DeviceLifecycleState`
    before use: *current* in particular is often read straight from an
    ORM attribute, which -- when the row was freshly materialized rather
    than found live in the session's identity map -- carries a plain
    ``str`` rather than the enum instance, since the column is declared
    as plain ``String`` with no Enum type decorator. ``.value`` access
    below would fail on that plain string; the coercion is a no-op for an
    already-genuine enum instance.
    """
    current = DeviceLifecycleState(current)
    target = DeviceLifecycleState(target)
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


def is_terminal(state: DeviceLifecycleState) -> bool:
    return not ALLOWED_TRANSITIONS.get(state, frozenset())


def is_stale(last_seen_at: datetime | None, *, now: datetime, threshold_minutes: int) -> bool:
    """Whether a device has gone quiet long enough to be treated as
    offline.

    ``last_seen_at is None`` (never reported at all) is stale by
    definition -- there is no evidence of it ever having been reachable.
    """
    if last_seen_at is None:
        return True
    return now - last_seen_at > timedelta(minutes=threshold_minutes)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_stale",
    "is_terminal",
    "validate_transition",
]
