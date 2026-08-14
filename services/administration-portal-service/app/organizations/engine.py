"""Organization lifecycle transitions.

**An organization only moves between adjacent, explicitly allowed
states.** ``ARCHIVED`` is the one terminal state -- an archived
organization is not reactivated in place; a genuinely returning
customer gets a new organization record.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import OrganizationStatus

_S = OrganizationStatus

ALLOWED_TRANSITIONS: dict[OrganizationStatus, frozenset[OrganizationStatus]] = {
    _S.ACTIVE: frozenset({_S.SUSPENDED, _S.ARCHIVED}),
    _S.SUSPENDED: frozenset({_S.ACTIVE, _S.ARCHIVED}),
    _S.ARCHIVED: frozenset(),
}


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: OrganizationStatus, target: OrganizationStatus
) -> TransitionResult:
    """Whether an organization may move from *current* to *target*.

    Both arguments are coerced through :class:`OrganizationStatus`
    before use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = OrganizationStatus(current)
    target = OrganizationStatus(target)
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
