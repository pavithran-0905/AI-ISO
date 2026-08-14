"""Tenant lifecycle transitions and limit-vs-usage classification.

**A tenant only moves between adjacent, explicitly allowed states.**
Skipping straight from ``PROVISIONING`` to ``SUSPENDED`` would suspend a
tenant that was never actually activated.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import TenantStatus

_S = TenantStatus

ALLOWED_TRANSITIONS: dict[TenantStatus, frozenset[TenantStatus]] = {
    _S.PROVISIONING: frozenset({_S.ACTIVE, _S.DELETING}),
    _S.ACTIVE: frozenset({_S.SUSPENDED, _S.MIGRATING, _S.DELETING}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.DELETING}),
    _S.MIGRATING: frozenset({_S.ACTIVE, _S.DELETING}),
    _S.DELETING: frozenset({_S.DELETED}),
    _S.DELETED: frozenset(),
}
"""Every valid next state. ``DELETED`` is the one truly terminal state."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: TenantStatus, target: TenantStatus) -> TransitionResult:
    """Whether a tenant may move from *current* to *target*.

    Both arguments are coerced through :class:`TenantStatus` before
    use, since a plain-``String``-typed column can carry a plain ``str``
    rather than the enum instance for a freshly materialized row.
    """
    current = TenantStatus(current)
    target = TenantStatus(target)
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


class TenantLimitStatus:
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


def classify_limit_status(used_value: float, limit_value: float, *, warning_fraction: float) -> str:
    """Classify a tenant's current standing against one of its limits.

    Raises:
        ValueError: On a negative *used_value*, or a non-positive
            *limit_value*.
    """
    if used_value < 0:
        raise ValueError(f"used_value must be non-negative; got {used_value}.")
    if limit_value <= 0:
        raise ValueError(f"limit_value must be positive; got {limit_value}.")
    if used_value >= limit_value:
        return TenantLimitStatus.EXCEEDED
    if used_value >= limit_value * warning_fraction:
        return TenantLimitStatus.WARNING
    return TenantLimitStatus.OK


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TenantLimitStatus",
    "TransitionRefusal",
    "TransitionResult",
    "classify_limit_status",
    "validate_transition",
]
