"""Rollback path validation, built on ``app.dependencies.engine``'s
numeric semantic-version comparison."""

from __future__ import annotations

from collections.abc import Iterable

from app.dependencies.engine import parse_semantic_version


def can_rollback_to(
    *, current_version: str, target_version: str, available_versions: Iterable[str]
) -> bool:
    """Whether a rollback from *current_version* to *target_version* is
    valid: *target_version* must be an older version than the one
    running now, and it must be a version this installation has
    actually seen before -- rollback restores a previously known-good
    state, it never jumps to an arbitrary or newer version."""
    if parse_semantic_version(target_version) >= parse_semantic_version(current_version):
        return False
    return target_version in set(available_versions)


__all__ = ["can_rollback_to"]
