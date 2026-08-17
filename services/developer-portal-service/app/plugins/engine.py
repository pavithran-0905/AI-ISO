"""Plugin submission publishing workflow and checksum verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.models.enums import PluginSubmissionStatus

_S = PluginSubmissionStatus

ALLOWED_TRANSITIONS: dict[PluginSubmissionStatus, frozenset[PluginSubmissionStatus]] = {
    _S.SUBMITTED: frozenset({_S.VALIDATING}),
    _S.VALIDATING: frozenset({_S.PENDING_APPROVAL, _S.REJECTED}),
    _S.PENDING_APPROVAL: frozenset({_S.APPROVED, _S.REJECTED}),
    _S.APPROVED: frozenset(),
    _S.REJECTED: frozenset({_S.SUBMITTED}),
}
"""``REJECTED -> SUBMITTED`` is the resubmission path -- a rejected
plugin can be corrected and resubmitted without starting a brand new
submission row. ``APPROVED`` is the one truly terminal state; a new
version is always a new submission."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(
    current: PluginSubmissionStatus, target: PluginSubmissionStatus
) -> TransitionResult:
    """Whether a plugin submission may move from *current* to *target*."""
    current = PluginSubmissionStatus(current)
    target = PluginSubmissionStatus(target)
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


def compute_checksum(content: bytes) -> str:
    """The SHA-256 checksum of a plugin archive's raw bytes."""
    return hashlib.sha256(content).hexdigest()


def verify_checksum(content: bytes, *, expected_checksum: str) -> bool:
    """Whether *content*'s own checksum matches *expected_checksum*."""
    return compute_checksum(content) == expected_checksum


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "compute_checksum",
    "validate_transition",
    "verify_checksum",
]
