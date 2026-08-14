"""Device configuration versioning.

**A configuration rollback selects an earlier row; it never
reconstructs one.** Every applied value is its own immutable row
(:class:`~app.models.operations.EdgeConfiguration`), so "roll back" is
just "activate an existing, already-applied version" -- there is nothing
to regenerate and therefore nothing that can regenerate incorrectly.
"""

from __future__ import annotations

from dataclasses import dataclass


class RollbackRefusal:
    NO_SUCH_VERSION = "no_such_version"
    ALREADY_ACTIVE = "already_active"


@dataclass(frozen=True, slots=True)
class RollbackValidation:
    is_valid: bool
    refusal: str | None
    detail: str


def validate_rollback(
    target_version: int, *, current_version: int, known_versions: frozenset[int]
) -> RollbackValidation:
    """Whether rolling a device's configuration back to *target_version*
    is allowed.

    Refuses a target that was never actually applied (not in
    *known_versions*) and a no-op rollback to the version already
    active.
    """
    if target_version == current_version:
        return RollbackValidation(
            is_valid=False,
            refusal=RollbackRefusal.ALREADY_ACTIVE,
            detail=f"Version {target_version} is already active.",
        )
    if target_version not in known_versions:
        return RollbackValidation(
            is_valid=False,
            refusal=RollbackRefusal.NO_SUCH_VERSION,
            detail=f"Version {target_version} was never applied to this device.",
        )
    return RollbackValidation(
        is_valid=True, refusal=None, detail=f"Rolling back to version {target_version}."
    )


__all__ = ["RollbackRefusal", "RollbackValidation", "validate_rollback"]
