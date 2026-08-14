"""Remote configuration scope matching and resolution.

A configuration entry with ``platform=None`` applies to every platform
in its own environment; a platform-scoped entry overrides the
platform-agnostic one for the same key, for that platform only. Only
enabled entries are ever eligible to apply -- a disabled entry is kept
for its own rollback history, not served to any client.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.models.enums import MobilePlatform


@dataclass(frozen=True, slots=True)
class ConfigurationEntry:
    """The minimal shape :func:`resolve_configuration` needs from a
    row -- decoupled from the ORM model so this stays a pure function."""

    key: str
    value: dict[str, Any]
    environment: str
    platform: MobilePlatform | None
    is_enabled: bool


def matches_scope(entry: ConfigurationEntry, *, platform: MobilePlatform, environment: str) -> bool:
    """Whether *entry* is eligible to apply for *platform* in
    *environment*."""
    if not entry.is_enabled:
        return False
    if entry.environment != environment:
        return False
    return entry.platform is None or entry.platform == platform


def resolve_configuration(
    entries: Sequence[ConfigurationEntry], *, platform: MobilePlatform, environment: str
) -> dict[str, Any]:
    """Merge every eligible entry into one effective configuration
    mapping, keyed by ``key``.

    Platform-scoped entries are applied after platform-agnostic ones,
    so a platform-specific override always wins regardless of the
    input order.
    """
    eligible = [
        entry
        for entry in entries
        if matches_scope(entry, platform=platform, environment=environment)
    ]
    global_entries = [entry for entry in eligible if entry.platform is None]
    scoped_entries = [entry for entry in eligible if entry.platform is not None]

    resolved: dict[str, Any] = {}
    for entry in global_entries:
        resolved[entry.key] = entry.value
    for entry in scoped_entries:
        resolved[entry.key] = entry.value
    return resolved


__all__ = ["ConfigurationEntry", "matches_scope", "resolve_configuration"]
