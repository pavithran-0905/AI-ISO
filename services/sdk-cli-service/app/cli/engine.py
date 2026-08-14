"""CLI update attempt lifecycle transitions.

**An update only moves between adjacent, explicitly allowed states.**
Skipping straight from ``PENDING`` to ``APPLIED`` would apply an update
that was never actually downloaded.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import CliUpdateStatus

_S = CliUpdateStatus

ALLOWED_TRANSITIONS: dict[CliUpdateStatus, frozenset[CliUpdateStatus]] = {
    _S.PENDING: frozenset({_S.DOWNLOADING, _S.FAILED}),
    _S.DOWNLOADING: frozenset({_S.APPLIED, _S.FAILED}),
    _S.APPLIED: frozenset(),
    _S.FAILED: frozenset({_S.PENDING}),
}
"""Every valid next state. ``APPLIED`` is terminal for that attempt; a
``FAILED`` attempt may be retried by moving back to ``PENDING``."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: CliUpdateStatus, target: CliUpdateStatus) -> TransitionResult:
    """Whether a CLI update attempt may move from *current* to
    *target*.

    Both arguments are coerced through :class:`CliUpdateStatus` before
    use, since a plain-``String``-typed column can carry a plain ``str``
    rather than the enum instance for a freshly materialized row.
    """
    current = CliUpdateStatus(current)
    target = CliUpdateStatus(target)
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
