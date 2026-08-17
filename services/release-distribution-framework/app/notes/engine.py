"""Release note classification."""

from __future__ import annotations

from app.models.enums import ReleaseNoteType

_SECURITY_RELEVANT_TYPES = frozenset({ReleaseNoteType.SECURITY_FIX})
_BREAKING_TYPES = frozenset({ReleaseNoteType.BREAKING_CHANGE})


def is_security_note(note_type: ReleaseNoteType) -> bool:
    """Whether a release note entry documents a security-relevant
    change."""
    return ReleaseNoteType(note_type) in _SECURITY_RELEVANT_TYPES


def is_breaking_note(note_type: ReleaseNoteType) -> bool:
    """Whether a release note entry documents a breaking change."""
    return ReleaseNoteType(note_type) in _BREAKING_TYPES


__all__ = ["is_breaking_note", "is_security_note"]
