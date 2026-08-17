"""Shared content publication lifecycle.

Reused across every content type this portal owns that follows the
same draft -> published -> archived shape: documentation pages,
tutorials, learning paths, sample projects, and knowledge articles --
one state machine, not five copies of an identical one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ContentStatus

_S = ContentStatus

ALLOWED_TRANSITIONS: dict[ContentStatus, frozenset[ContentStatus]] = {
    _S.DRAFT: frozenset({_S.PUBLISHED}),
    _S.PUBLISHED: frozenset({_S.ARCHIVED, _S.DRAFT}),
    _S.ARCHIVED: frozenset({_S.DRAFT}),
}
"""``PUBLISHED -> DRAFT`` is the unpublish path (content pulled back for
rework); ``ARCHIVED -> DRAFT`` is a deliberate revival. Nothing here is
truly terminal -- archived content can always be brought back as a
fresh draft, unlike a revoked credential or a sunset API version."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: ContentStatus, target: ContentStatus) -> TransitionResult:
    """Whether a piece of content may move from *current* to *target*.

    Both arguments are coerced through :class:`ContentStatus` before
    use, since a plain-``String``-typed column can carry a plain
    ``str`` rather than the enum instance for a freshly materialized
    row.
    """
    current = ContentStatus(current)
    target = ContentStatus(target)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        allowed_names = ", ".join(sorted(state.value for state in allowed))
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.INVALID_TRANSITION,
            detail=(
                f"{current.value} cannot transition to {target.value}; "
                f"allowed next states are: {allowed_names or 'none'}."
            ),
        )
    return TransitionResult(
        is_allowed=True, refusal=None, detail=f"{current.value} -> {target.value} is allowed."
    )


__all__ = ["ALLOWED_TRANSITIONS", "TransitionRefusal", "TransitionResult", "validate_transition"]
