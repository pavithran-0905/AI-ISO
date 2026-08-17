"""Dependency version parsing, comparison, and compatibility
classification.

``SemanticVersion`` and its comparison are also reused, unmodified, by
``app.upgrade.engine`` and ``app.rollback.engine`` -- one numeric
version-comparison implementation, not three, mirroring
``services/public-api-platform``'s own ``SemanticVersion`` precedent
(Prompt 073). Each AI-IOS service keeps its own copy rather than
importing another service's package, since services never import each
other's code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import CheckResultStatus

_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True, slots=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int


def parse_semantic_version(version_label: str) -> SemanticVersion:
    """Parse a ``MAJOR.MINOR.PATCH`` version label, tolerating a
    leading ``v`` and an ignored trailing pre-release/build suffix
    (e.g. ``v1.2.3-beta.1`` parses the same as ``1.2.3``).

    Raises:
        ValueError: If *version_label* does not start with three
            numeric dot-separated components.
    """
    match = _VERSION_PATTERN.match(version_label.strip())
    if match is None:
        raise ValueError(f"{version_label!r} is not a valid MAJOR.MINOR.PATCH version label.")
    major, minor, patch = (int(part) for part in match.groups())
    return SemanticVersion(major=major, minor=minor, patch=patch)


def is_version_at_least(found: str, required: str) -> bool:
    """Whether *found* is numerically greater than or equal to
    *required*."""
    return parse_semantic_version(found) >= parse_semantic_version(required)


def classify_dependency_check(*, required_version: str, found_version: str) -> CheckResultStatus:
    """Classify one dependency's compatibility outcome.

    A missing (empty) ``found_version`` is always ``FAILED`` -- the
    dependency was not found at all. A ``found_version`` older than
    ``required_version`` is ``FAILED``. A ``found_version`` on a newer
    *major* line than required is ``WARNING`` (compatibility is not
    guaranteed across a major version boundary); anything else that
    meets the minimum is ``PASSED``.
    """
    if not found_version.strip():
        return CheckResultStatus.FAILED
    required = parse_semantic_version(required_version)
    found = parse_semantic_version(found_version)
    if found < required:
        return CheckResultStatus.FAILED
    if found.major > required.major:
        return CheckResultStatus.WARNING
    return CheckResultStatus.PASSED


__all__ = [
    "SemanticVersion",
    "classify_dependency_check",
    "is_version_at_least",
    "parse_semantic_version",
]
