"""Semantic version parsing, comparison, compatibility, and
breaking-change detection.

**A version compatibility check is purely numeric, never a string
comparison.** ``"9.0.0" < "10.0.0"`` is false as strings but true as
versions -- every comparison here parses first.
"""

from __future__ import annotations

from dataclasses import dataclass

_VERSION_PARTS = 3


@dataclass(frozen=True, slots=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int


def parse_version(version: str) -> SemanticVersion:
    """Parse a ``MAJOR.MINOR.PATCH`` string into a comparable
    :class:`SemanticVersion`.

    Raises:
        ValueError: If *version* is not exactly three dot-separated
            non-negative integers.
    """
    parts = version.split(".")
    if len(parts) != _VERSION_PARTS:
        raise ValueError(f"version must be MAJOR.MINOR.PATCH; got {version!r}.")
    try:
        major, minor, patch = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"version must be MAJOR.MINOR.PATCH; got {version!r}.") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ValueError(f"version parts must be non-negative; got {version!r}.")
    return SemanticVersion(major=major, minor=minor, patch=patch)


def is_breaking_change(previous_version: str, next_version: str) -> bool:
    """Whether *next_version* is a breaking change from
    *previous_version* -- a major-version bump, per semantic
    versioning."""
    previous = parse_version(previous_version)
    next_ = parse_version(next_version)
    return next_.major > previous.major


def is_update_available(current_version: str, latest_version: str) -> bool:
    """Whether *latest_version* is newer than *current_version*."""
    return parse_version(latest_version) > parse_version(current_version)


def is_api_compatible(client_api_version: str, *, minimum_api_version: str) -> bool:
    """Whether a client's own reported API compatibility version meets
    a minimum requirement."""
    return parse_version(client_api_version) >= parse_version(minimum_api_version)


__all__ = [
    "SemanticVersion",
    "is_api_compatible",
    "is_breaking_change",
    "is_update_available",
    "parse_version",
]
