"""Cluster lifecycle state transitions.

**A cluster only moves between adjacent, explicitly allowed states.**
Skipping straight from ``DISCOVERED`` to ``ACTIVE`` would mean a cluster
this service has never validated or provisioned is treated as fully
operational -- every hop in between exists because something real has to
happen at that step, not because the state machine likes long chains.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ClusterLifecycleState

_S = ClusterLifecycleState

ALLOWED_TRANSITIONS: dict[ClusterLifecycleState, frozenset[ClusterLifecycleState]] = {
    _S.DISCOVERED: frozenset({_S.REGISTERED, _S.FAILED}),
    _S.REGISTERED: frozenset({_S.VALIDATING, _S.FAILED}),
    _S.VALIDATING: frozenset({_S.VALIDATED, _S.FAILED}),
    _S.VALIDATED: frozenset({_S.PROVISIONING, _S.FAILED}),
    _S.PROVISIONING: frozenset({_S.PROVISIONED, _S.FAILED}),
    _S.PROVISIONED: frozenset({_S.CONFIGURING, _S.FAILED}),
    _S.CONFIGURING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.ACTIVE: frozenset(
        {_S.UPGRADING, _S.SCALING, _S.MAINTENANCE, _S.SUSPENDED, _S.DECOMMISSIONING, _S.FAILED}
    ),
    _S.UPGRADING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.SCALING: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.MAINTENANCE: frozenset({_S.ACTIVE, _S.FAILED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.DECOMMISSIONING, _S.FAILED}),
    _S.DECOMMISSIONING: frozenset({_S.DECOMMISSIONED, _S.FAILED}),
    _S.DECOMMISSIONED: frozenset({_S.ARCHIVED}),
    _S.ARCHIVED: frozenset(),
    _S.FAILED: frozenset({_S.REGISTERED, _S.DECOMMISSIONING}),
}
"""Every valid next state. ``ARCHIVED`` has none -- it is the one truly
terminal state; even ``DECOMMISSIONED`` can still move to ``ARCHIVED``,
and ``FAILED`` can still retry (back to ``REGISTERED``) or be
decommissioned outright."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: ClusterLifecycleState, target: ClusterLifecycleState
) -> TransitionResult:
    """Whether a cluster may move from *current* to *target*.

    Both arguments are coerced through :class:`ClusterLifecycleState`
    before use: *current* in particular is often read straight from an
    ORM attribute, which -- when the row was freshly materialized rather
    than found live in the session's identity map -- carries a plain
    ``str`` rather than the enum instance, since the column is declared
    as plain ``String`` with no Enum type decorator. ``.value`` access
    below would fail on that plain string; the coercion is a no-op for an
    already-genuine enum instance.
    """
    current = ClusterLifecycleState(current)
    target = ClusterLifecycleState(target)
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


def is_terminal(state: ClusterLifecycleState) -> bool:
    return not ALLOWED_TRANSITIONS.get(state, frozenset())


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_terminal",
    "validate_transition",
]
