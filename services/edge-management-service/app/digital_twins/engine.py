"""Digital twin synchronization classification.

**Sync status is a comparison of two state hashes, never a claim about
intent this service cannot see** -- the same discipline
``app.gitops.engine`` established in
``services/multi-cluster-management-service``.
"""

from __future__ import annotations

from app.models.enums import SyncStatus


def classify_twin_sync(
    desired_state_hash: str | None, live_state_hash: str | None, *, is_syncing: bool
) -> SyncStatus:
    """Classify a digital twin's sync state against its physical
    device's last-reported state.

    A sync already in progress is reported ``IN_PROGRESS`` regardless of
    what the hashes currently say. Either hash being unavailable is
    ``PENDING``, never assumed in sync.
    """
    if is_syncing:
        return SyncStatus.IN_PROGRESS
    if desired_state_hash is None or live_state_hash is None:
        return SyncStatus.PENDING
    if desired_state_hash == live_state_hash:
        return SyncStatus.COMPLETED
    return SyncStatus.CONFLICT


__all__ = ["classify_twin_sync"]
