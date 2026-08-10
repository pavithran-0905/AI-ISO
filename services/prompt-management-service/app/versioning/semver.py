"""Prompt semantic versioning (docs/061 "VERSION MANAGEMENT").

Comparison and compatibility reuse ``shared_core.plugins.versioning``
directly -- the same real semver machinery Prompts 058 and 059 already
reused. What that module does not provide, and this one adds, is
**bumping**: computing the next version from a current one and a chosen
component. A plugin's version arrives from its own manifest, so nothing
in the platform ever needed to derive one before.

``INITIAL_VERSION`` is ``1.0.0`` rather than ``0.1.0``. A prompt's
first published revision is a real, usable artefact that other services
resolve by name -- there is no pre-release phase for it the way there
is for a library API.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.plugins.versioning import is_downgrade, is_upgrade

from app.models.enums import VersionBump

INITIAL_VERSION = "1.0.0"
_SEMVER_PARTS = 3


@dataclass(frozen=True, slots=True)
class VersionDiff:
    """How two revisions of one prompt differ ("Comparison")."""

    from_version: str
    to_version: str
    bump: VersionBump | None
    is_forward: bool
    added_lines: tuple[str, ...] = ()
    removed_lines: tuple[str, ...] = ()
    token_delta: int = 0

    @property
    def is_identical(self) -> bool:
        """Whether the two bodies are the same text."""
        return not self.added_lines and not self.removed_lines


def is_valid(version_number: str) -> bool:
    """Whether *version_number* is a version this module can work with.

    Checks :func:`_parts`, **not** ``shared_core``'s own
    ``parse_version``. The two genuinely disagree: ``parse_version``
    accepts a two-part ``"1.2"``, while everything here requires all
    three components. Validating against the looser one would let
    ``is_valid("1.2")`` return ``True`` and then have :func:`bump`
    raise on the very next line -- a validator that disagrees with the
    thing it is validating for is worse than no validator.
    """
    try:
        _parts(version_number)
    except ValueError:
        return False
    return True


def _parts(version_number: str) -> tuple[int, int, int]:
    """Split into ``(major, minor, patch)``.

    Raises:
        ValueError: If *version_number* is not ``major.minor.patch``.
    """
    pieces = version_number.split(".")
    if len(pieces) != _SEMVER_PARTS:
        raise ValueError(f"Version {version_number!r} is not major.minor.patch.")
    try:
        major, minor, patch = (int(piece) for piece in pieces)
    except ValueError as exc:
        raise ValueError(f"Version {version_number!r} has a non-numeric component.") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ValueError(f"Version {version_number!r} has a negative component.")
    return major, minor, patch


def bump(version_number: str, component: VersionBump) -> str:
    """The next version after *version_number* for *component*.

    Bumping major zeroes minor and patch; bumping minor zeroes patch.
    That is what makes version ordering total -- ``1.2.3`` to
    ``2.0.0``, never ``2.2.3``, which would leave ``2.0.0`` and
    ``2.1.0`` permanently unreachable.

    Raises:
        ValueError: If *version_number* is not valid semver.
    """
    major, minor, patch = _parts(version_number)
    if component == VersionBump.MAJOR:
        return f"{major + 1}.0.0"
    if component == VersionBump.MINOR:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def next_version(current: str | None, component: VersionBump = VersionBump.PATCH) -> str:
    """The next version, treating "no current version" as the first one.

    Raises:
        ValueError: If *current* is set but not valid semver.
    """
    if current is None or not current.strip():
        return INITIAL_VERSION
    return bump(current, component)


def infer_bump(from_version: str, to_version: str) -> VersionBump | None:
    """Which component changed between two versions, or ``None``.

    ``None`` means they are identical or differ in a way that is not a
    single clean bump -- a rollback, or a hand-edited version string.

    Raises:
        ValueError: If either version is not valid semver.
    """
    from_major, from_minor, _ = _parts(from_version)
    to_major, to_minor, to_patch = _parts(to_version)
    if to_major != from_major:
        return VersionBump.MAJOR
    if to_minor != from_minor:
        return VersionBump.MINOR
    if to_patch != _parts(from_version)[2]:
        return VersionBump.PATCH
    return None


def compare_bodies(
    from_version: str,
    to_version: str,
    from_body: str,
    to_body: str,
    *,
    token_delta: int = 0,
) -> VersionDiff:
    """A line-level diff between two revisions ("Comparison").

    Deliberately set-based rather than a positional unified diff: what
    a reviewer of a *prompt* needs is "which instructions appeared and
    which disappeared", not which line numbers shifted when a paragraph
    moved.

    Raises:
        ValueError: If either version is not valid semver.
    """
    from_lines = [line.strip() for line in from_body.splitlines() if line.strip()]
    to_lines = [line.strip() for line in to_body.splitlines() if line.strip()]
    from_set, to_set = set(from_lines), set(to_lines)

    return VersionDiff(
        from_version=from_version,
        to_version=to_version,
        bump=infer_bump(from_version, to_version),
        is_forward=is_upgrade(from_version, to_version),
        added_lines=tuple(line for line in to_lines if line not in from_set),
        removed_lines=tuple(line for line in from_lines if line not in to_set),
        token_delta=token_delta,
    )


def sort_versions(version_numbers: list[str]) -> list[str]:
    """Sort semver strings oldest-first.

    Sorts by parsed numeric components, never lexically: ``"10.0.0"``
    sorts *before* ``"9.0.0"`` as a string, which would silently make a
    tenth major version look older than the ninth.

    Raises:
        ValueError: If any entry is not valid semver.
    """
    return sorted(version_numbers, key=_parts)


__all__ = [
    "INITIAL_VERSION",
    "VersionDiff",
    "bump",
    "compare_bodies",
    "infer_bump",
    "is_downgrade",
    "is_upgrade",
    "is_valid",
    "next_version",
    "sort_versions",
]
