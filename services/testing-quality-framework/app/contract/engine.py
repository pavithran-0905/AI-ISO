"""Contract version-compatibility classification.

Reuses the same numeric ``MAJOR.MINOR.PATCH`` comparison shape every
prior version-comparison engine in this codebase uses, kept as its own
self-contained copy since services never import each other's code.
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
    leading ``v`` and an ignored trailing pre-release/build suffix.

    Raises:
        ValueError: If *version_label* does not start with three
            numeric dot-separated components.
    """
    match = _VERSION_PATTERN.match(version_label.strip())
    if match is None:
        raise ValueError(f"{version_label!r} is not a valid MAJOR.MINOR.PATCH version label.")
    major, minor, patch = (int(part) for part in match.groups())
    return SemanticVersion(major=major, minor=minor, patch=patch)


def classify_contract_compatibility(
    *, provider_version: str, consumer_version: str
) -> CheckResultStatus:
    """Classify whether a consumer built against *consumer_version* is
    compatible with a provider now running *provider_version*: an
    identical or newer-patch/minor provider is ``PASSED`` (backward
    compatible); a provider on a newer major line is ``WARNING``
    (compatibility not guaranteed); a provider *older* than the
    consumer expected is ``FAILED``."""
    provider = parse_semantic_version(provider_version)
    consumer = parse_semantic_version(consumer_version)
    if provider < consumer:
        return CheckResultStatus.FAILED
    if provider.major > consumer.major:
        return CheckResultStatus.WARNING
    return CheckResultStatus.PASSED


__all__ = ["SemanticVersion", "classify_contract_compatibility", "parse_semantic_version"]
