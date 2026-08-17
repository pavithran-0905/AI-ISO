"""Semantic version parsing/comparison and compatibility
classification.

``SemanticVersion`` and its comparison are reused, unmodified, by
``app.dependencies.engine`` and ``app.rollback.engine`` -- one numeric
version-comparison implementation, not three, mirroring
``services/installation-deployment-service``'s own precedent (Prompt
075). Each AI-IOS service keeps its own copy rather than importing
another service's package, since services never import each other's
code.
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


def classify_compatibility(*, from_version: str, to_version: str) -> CheckResultStatus:
    """Classify the compatibility outcome of moving from *from_version*
    to *to_version*.

    A downgrade or no-op is always ``FAILED`` -- compatibility
    validation is only meaningful for a forward move. Crossing a major
    version boundary is ``WARNING`` (compatibility is not guaranteed
    across one); anything else forward is ``PASSED``.
    """
    from_semver = parse_semantic_version(from_version)
    to_semver = parse_semantic_version(to_version)
    if to_semver <= from_semver:
        return CheckResultStatus.FAILED
    if to_semver.major > from_semver.major:
        return CheckResultStatus.WARNING
    return CheckResultStatus.PASSED


__all__ = ["SemanticVersion", "classify_compatibility", "parse_semantic_version"]
