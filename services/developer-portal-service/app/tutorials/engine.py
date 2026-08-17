"""Learning path composition math.

**Per-developer completion is not persisted anywhere in this build.**
docs/074's own DATABASE TABLES section -- the authoritative table list
this service's 24 tables were built from exactly -- has no completion-
tracking table, despite "Progress Tracking" being named under LEARNING
CENTER. Consistent with every other AI-IOS "declared seam" (069's
caller-reported billing outcomes, 071's caller-reported CLI update
outcomes), ``TutorialCompletedEvent`` is published on a caller's own
report that a tutorial was completed, with no corresponding row this
service itself writes to remember it happened -- there is nowhere in
the schema that fact could live.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.enums import TutorialDifficulty

_DIFFICULTY_ORDER: dict[TutorialDifficulty, int] = {
    TutorialDifficulty.BEGINNER: 0,
    TutorialDifficulty.INTERMEDIATE: 1,
    TutorialDifficulty.ADVANCED: 2,
}
_MAX_DIFFICULTY_JUMP = 1


def total_estimated_minutes(tutorial_minutes: Sequence[int]) -> int:
    """The total estimated duration of a learning path's own ordered
    tutorials."""
    return sum(tutorial_minutes)


def is_appropriate_next_difficulty(
    current: TutorialDifficulty, next_difficulty: TutorialDifficulty
) -> bool:
    """Whether *next_difficulty* is a reasonable next step after
    *current* within one learning path -- never more than one level up
    at a time (beginner -> intermediate is fine; beginner -> advanced
    skips a step a learner would struggle with), though dropping back
    down is always fine (a path may deliberately revisit fundamentals)."""
    current_rank = _DIFFICULTY_ORDER[TutorialDifficulty(current)]
    next_rank = _DIFFICULTY_ORDER[TutorialDifficulty(next_difficulty)]
    return next_rank - current_rank <= _MAX_DIFFICULTY_JUMP


__all__ = ["is_appropriate_next_difficulty", "total_estimated_minutes"]
