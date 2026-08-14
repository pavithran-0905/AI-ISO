"""Service catalog item approval workflow transitions.

**A catalog item only becomes self-service-provisionable after an
explicit approval.** Skipping straight from ``DRAFT`` to ``APPROVED``
would let an unreviewed template reach self-service provisioning.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import CatalogItemStatus

_S = CatalogItemStatus

ALLOWED_TRANSITIONS: dict[CatalogItemStatus, frozenset[CatalogItemStatus]] = {
    _S.DRAFT: frozenset({_S.PENDING_APPROVAL}),
    _S.PENDING_APPROVAL: frozenset({_S.APPROVED, _S.REJECTED}),
    _S.APPROVED: frozenset({_S.DEPRECATED}),
    _S.REJECTED: frozenset({_S.DRAFT}),
    _S.DEPRECATED: frozenset(),
}
"""Every valid next state. ``DEPRECATED`` is the one terminal state;
``REJECTED`` can be revised and resubmitted from ``DRAFT``."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: CatalogItemStatus, target: CatalogItemStatus) -> TransitionResult:
    """Whether a catalog item may move from *current* to *target*."""
    current = CatalogItemStatus(current)
    target = CatalogItemStatus(target)
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


def is_provisionable(status: CatalogItemStatus) -> bool:
    """Whether a catalog item may be used for self-service
    provisioning -- only an ``APPROVED`` item may."""
    return CatalogItemStatus(status) == CatalogItemStatus.APPROVED


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "is_provisionable",
    "validate_transition",
]
