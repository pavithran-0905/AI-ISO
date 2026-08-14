"""Device trust lifecycle transitions.

**A device only moves between adjacent, explicitly allowed states.**
Skipping straight from ``PENDING`` to some post-revocation state would
approve a device nobody ever actually reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import DeviceTrustStatus

_S = DeviceTrustStatus

ALLOWED_TRANSITIONS: dict[DeviceTrustStatus, frozenset[DeviceTrustStatus]] = {
    _S.PENDING: frozenset({_S.APPROVED, _S.REVOKED}),
    _S.APPROVED: frozenset({_S.REVOKED}),
    _S.REVOKED: frozenset(),
}
"""Every valid next state. ``REVOKED`` is the one truly terminal state
-- a revoked (lost/stolen/compromised) device is never silently
re-trusted; re-enrollment is a brand new device record."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: DeviceTrustStatus, target: DeviceTrustStatus) -> TransitionResult:
    """Whether a device may move from *current* to *target*.

    Both arguments are coerced through :class:`DeviceTrustStatus`
    before use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = DeviceTrustStatus(current)
    target = DeviceTrustStatus(target)
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
