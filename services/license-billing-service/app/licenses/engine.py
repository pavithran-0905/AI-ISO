"""License lifecycle transitions and seat limit validation.

**A license only moves between adjacent, explicitly allowed states.**
Skipping straight from ``ISSUED`` to ``ACTIVE`` without activation would
treat a license nobody has actually activated as in use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import LicenseStatus

_S = LicenseStatus

ALLOWED_TRANSITIONS: dict[LicenseStatus, frozenset[LicenseStatus]] = {
    _S.ISSUED: frozenset({_S.ACTIVE, _S.REVOKED, _S.EXPIRED}),
    _S.ACTIVE: frozenset({_S.SUSPENDED, _S.REVOKED, _S.EXPIRED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.REVOKED, _S.EXPIRED}),
    _S.REVOKED: frozenset(),
    _S.EXPIRED: frozenset({_S.ACTIVE}),
}
"""Every valid next state. ``REVOKED`` is the one truly terminal
state; ``EXPIRED`` can still be reactivated by a renewal."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: LicenseStatus, target: LicenseStatus) -> TransitionResult:
    """Whether a license may move from *current* to *target*.

    Both arguments are coerced through :class:`LicenseStatus` before
    use, since a plain-``String``-typed column can carry a plain ``str``
    rather than the enum instance for a freshly materialized row.
    """
    current = LicenseStatus(current)
    target = LicenseStatus(target)
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


def is_expired(expires_at: datetime | None, *, now: datetime) -> bool:
    """Whether a license has passed its expiry.

    ``expires_at is None`` means "never expires" -- a perpetual
    license.
    """
    return expires_at is not None and expires_at <= now


def has_seat_available(*, seat_limit: int | None, active_activation_count: int) -> bool:
    """Whether one more seat may be activated.

    ``seat_limit is None`` means unlimited seats -- always available.

    Raises:
        ValueError: On a negative *active_activation_count*.
    """
    if active_activation_count < 0:
        raise ValueError(
            f"active_activation_count must be non-negative; got {active_activation_count}."
        )
    if seat_limit is None:
        return True
    return active_activation_count < seat_limit


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "has_seat_available",
    "is_expired",
    "validate_transition",
]
