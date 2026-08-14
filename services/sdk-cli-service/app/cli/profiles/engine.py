"""Default-profile selection.

**At most one profile is ever default.** Marking a new profile default
never leaves a stale second default lying around -- this engine names
exactly which other profiles must be unset, so the service layer never
has to reimplement that invariant.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID


def profiles_to_unset(existing_default_ids: Sequence[UUID], *, new_default_id: UUID) -> list[UUID]:
    """Every currently-default profile id that must be unset now that
    *new_default_id* is becoming the default.

    *new_default_id* itself is never included, even if it already
    appears in *existing_default_ids* -- setting the current default
    default again is a no-op, not a self-unset.
    """
    return [profile_id for profile_id in existing_default_ids if profile_id != new_default_id]


__all__ = ["profiles_to_unset"]
