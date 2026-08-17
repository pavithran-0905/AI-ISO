"""Upgrade path validation, built on ``app.dependencies.engine``'s
numeric semantic-version comparison."""

from __future__ import annotations

from app.dependencies.engine import parse_semantic_version


def is_upgrade_path_valid(*, from_version: str, to_version: str) -> bool:
    """Whether an upgrade from *from_version* to *to_version* moves
    strictly forward. Downgrades and no-op "upgrades" to the same
    version are not valid upgrade paths -- that is what rollback and a
    no-op are for, respectively."""
    return parse_semantic_version(to_version) > parse_semantic_version(from_version)


def is_major_upgrade(*, from_version: str, to_version: str) -> bool:
    """Whether an upgrade crosses a major version boundary -- a signal
    worth surfacing distinctly, since a major bump is more likely to
    carry breaking changes than a minor or patch one."""
    return parse_semantic_version(to_version).major > parse_semantic_version(from_version).major


__all__ = ["is_major_upgrade", "is_upgrade_path_valid"]
