"""SDK release lifecycle transitions.

**A release only moves between adjacent, explicitly allowed states.**
Skipping straight from ``DRAFT`` to ``DEPRECATED`` would deprecate a
version nobody ever actually published.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ReleaseStatus

_S = ReleaseStatus

ALLOWED_TRANSITIONS: dict[ReleaseStatus, frozenset[ReleaseStatus]] = {
    _S.DRAFT: frozenset({_S.PUBLISHED}),
    _S.PUBLISHED: frozenset({_S.DEPRECATED, _S.YANKED}),
    _S.DEPRECATED: frozenset({_S.YANKED}),
    _S.YANKED: frozenset(),
}
"""Every valid next state. ``YANKED`` is the one truly terminal state --
a yanked release is never brought back; a fixed version is a new
release."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: ReleaseStatus, target: ReleaseStatus) -> TransitionResult:
    """Whether an SDK release may move from *current* to *target*.

    Both arguments are coerced through :class:`ReleaseStatus` before
    use, since a plain-``String``-typed column can carry a plain ``str``
    rather than the enum instance for a freshly materialized row.
    """
    current = ReleaseStatus(current)
    target = ReleaseStatus(target)
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
