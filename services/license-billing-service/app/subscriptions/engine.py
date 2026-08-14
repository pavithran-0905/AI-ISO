"""Subscription lifecycle transitions and renewal/grace-period
decisions.

**A subscription only moves between adjacent, explicitly allowed
states.** A trial that never converted cannot silently become
``ACTIVE`` -- something (a payment, an explicit conversion) has to
happen at that step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import SubscriptionStatus

_S = SubscriptionStatus

ALLOWED_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    _S.TRIAL: frozenset({_S.ACTIVE, _S.CANCELLED, _S.EXPIRED}),
    _S.ACTIVE: frozenset({_S.SUSPENDED, _S.PENDING_RENEWAL, _S.CANCELLED, _S.EXPIRED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.CANCELLED, _S.EXPIRED}),
    _S.PENDING_RENEWAL: frozenset({_S.ACTIVE, _S.EXPIRED, _S.CANCELLED}),
    _S.CANCELLED: frozenset(),
    _S.EXPIRED: frozenset({_S.ACTIVE}),
}
"""Every valid next state. ``CANCELLED`` is the one truly terminal
state; ``EXPIRED`` can still be reactivated by a late renewal."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: SubscriptionStatus, target: SubscriptionStatus
) -> TransitionResult:
    """Whether a subscription may move from *current* to *target*.

    Both arguments are coerced through :class:`SubscriptionStatus`
    before use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = SubscriptionStatus(current)
    target = SubscriptionStatus(target)
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


def is_within_grace_period(
    current_period_end: datetime, *, now: datetime, grace_period_days: int
) -> bool:
    """Whether *now* is still within the grace period after a
    subscription's current period ended.

    Raises:
        ValueError: On a negative *grace_period_days*.
    """
    if grace_period_days < 0:
        raise ValueError(f"grace_period_days must be non-negative; got {grace_period_days}.")
    return current_period_end <= now <= current_period_end + timedelta(days=grace_period_days)


def is_renewal_due(
    current_period_end: datetime, *, now: datetime, reminder_days_before: int
) -> bool:
    """Whether a subscription's renewal reminder window has begun.

    Raises:
        ValueError: On a non-positive *reminder_days_before*.
    """
    if reminder_days_before < 1:
        raise ValueError(f"reminder_days_before must be at least 1; got {reminder_days_before}.")
    return now >= current_period_end - timedelta(days=reminder_days_before)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_renewal_due",
    "is_within_grace_period",
    "validate_transition",
]
