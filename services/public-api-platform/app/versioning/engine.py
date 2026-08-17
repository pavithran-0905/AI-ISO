"""API semantic versioning, breaking-change detection, and version
lifecycle transitions.

Version comparison is always numeric, never lexical --
``"9.0.0" < "10.0.0"`` as strings is ``False``; as versions it must be
``True``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import ApiVersionStatus

_PART_COUNT = 3


@dataclass(frozen=True, slots=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int


def parse_version(label: str) -> SemanticVersion:
    """Parse a ``MAJOR.MINOR.PATCH`` version label.

    Raises:
        ValueError: If *label* is not exactly three non-negative
            integer parts.
    """
    parts = label.split(".")
    if len(parts) != _PART_COUNT:
        raise ValueError(f"{label!r} is not a valid MAJOR.MINOR.PATCH version label.")
    try:
        major, minor, patch = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{label!r} is not a valid MAJOR.MINOR.PATCH version label.") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ValueError(f"{label!r} has a negative version part, which is not allowed.")
    return SemanticVersion(major, minor, patch)


def is_breaking_change(current: str, candidate: str) -> bool:
    """Whether *candidate* is a major-version bump over *current* --
    the one kind of change docs/073 requires detecting automatically."""
    current_version = parse_version(current)
    candidate_version = parse_version(candidate)
    return candidate_version.major > current_version.major


# ---- lifecycle transitions -----------------------------------------------------------------

_S = ApiVersionStatus

ALLOWED_TRANSITIONS: dict[ApiVersionStatus, frozenset[ApiVersionStatus]] = {
    _S.DRAFT: frozenset({_S.RELEASED}),
    _S.RELEASED: frozenset({_S.DEPRECATED}),
    _S.DEPRECATED: frozenset({_S.SUNSET}),
    _S.SUNSET: frozenset(),
}
"""Strictly linear: a version is drafted, released, deprecated, and
finally sunset -- there is no path back to an earlier stage, and
``SUNSET`` is terminal."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: ApiVersionStatus, target: ApiVersionStatus) -> TransitionResult:
    """Whether an API version may move from *current* to *target*."""
    current = ApiVersionStatus(current)
    target = ApiVersionStatus(target)
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


def is_deprecation_due(*, deprecated_at: datetime | None, now: datetime) -> bool:
    """Whether a version's own planned deprecation date has arrived."""
    if deprecated_at is None:
        return False
    return now >= deprecated_at


def is_sunset_due(*, sunset_at: datetime | None, now: datetime) -> bool:
    """Whether a version's own planned sunset date has arrived."""
    if sunset_at is None:
        return False
    return now >= sunset_at


__all__ = [
    "ALLOWED_TRANSITIONS",
    "SemanticVersion",
    "TransitionRefusal",
    "TransitionResult",
    "is_breaking_change",
    "is_deprecation_due",
    "is_sunset_due",
    "parse_version",
    "validate_transition",
]
