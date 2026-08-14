"""Push notification delivery lifecycle and retry eligibility."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import NotificationDeliveryStatus, PushTokenStatus

_N = NotificationDeliveryStatus

DELIVERY_TRANSITIONS: dict[NotificationDeliveryStatus, frozenset[NotificationDeliveryStatus]] = {
    _N.PENDING: frozenset({_N.DELIVERED, _N.FAILED}),
    _N.FAILED: frozenset({_N.PENDING}),
    _N.DELIVERED: frozenset({_N.READ}),
    _N.READ: frozenset(),
}
"""``FAILED -> PENDING`` is the retry path (bounded by
``is_retry_eligible``); ``DELIVERED -> READ`` records the client's own
read receipt; ``READ`` is the one truly terminal state."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: NotificationDeliveryStatus, target: NotificationDeliveryStatus
) -> TransitionResult:
    """Whether a notification may move from *current* to *target*."""
    current = NotificationDeliveryStatus(current)
    target = NotificationDeliveryStatus(target)
    allowed = DELIVERY_TRANSITIONS.get(current, frozenset())
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


def is_retry_eligible(*, retry_count: int, max_retry_count: int) -> bool:
    """Whether a failed delivery attempt has retries left."""
    return retry_count < max_retry_count


def is_push_token_usable(status: PushTokenStatus) -> bool:
    """Whether a registered push token may still be sent to.

    Coerces through :class:`PushTokenStatus` first, since a freshly
    materialized row's ``status`` column comes back as a plain ``str``.
    """
    return PushTokenStatus(status) == PushTokenStatus.ACTIVE


__all__ = [
    "DELIVERY_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_push_token_usable",
    "is_retry_eligible",
    "validate_transition",
]
