"""GitOps sync classification.

**Sync status is a comparison of two hashes, never a claim about intent
this service cannot see.** Whether a cluster's live state matches what
Git declares is a fact this engine can establish; whether that
mismatch is *expected* (a deploy in progress) is exactly what
``is_syncing`` exists to distinguish from unexpected drift.
"""

from __future__ import annotations

from app.models.enums import SyncStatus


def classify_sync(
    desired_state_hash: str | None, live_state_hash: str | None, *, is_syncing: bool
) -> SyncStatus:
    """Classify a GitOps application's sync state.

    A sync already in progress is reported ``SYNCING`` regardless of
    what the hashes currently say -- a mismatch mid-sync is expected, not
    drift. Either hash being unavailable (nothing observed yet on one
    side) is ``UNKNOWN``, never assumed in sync.
    """
    if is_syncing:
        return SyncStatus.SYNCING
    if desired_state_hash is None or live_state_hash is None:
        return SyncStatus.UNKNOWN
    if desired_state_hash == live_state_hash:
        return SyncStatus.IN_SYNC
    return SyncStatus.OUT_OF_SYNC


__all__ = ["classify_sync"]
