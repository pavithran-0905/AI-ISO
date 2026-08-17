"""Dependency version-compatibility classification, built on
``app.compatibility.engine``'s numeric semantic-version comparison."""

from __future__ import annotations

from app.compatibility.engine import parse_semantic_version
from app.models.enums import CheckResultStatus


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


__all__ = ["classify_dependency_check"]
