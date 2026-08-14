"""Digital twin sync classification.

A thin wrapper over ``app.digital_twins.engine``'s pure classification --
there is no dedicated digital-twin table; a twin's sync state is
classified on demand from whatever state hashes the caller (an API route
or worker) currently has in hand, matching how
``services/multi-cluster-management-service`` classifies GitOps sync
without a dedicated table either.
"""

from __future__ import annotations

from app.digital_twins.engine import classify_twin_sync
from app.models.enums import SyncStatus


class DigitalTwinService:
    def classify(
        self, desired_state_hash: str | None, live_state_hash: str | None, *, is_syncing: bool
    ) -> SyncStatus:
        return classify_twin_sync(desired_state_hash, live_state_hash, is_syncing=is_syncing)


__all__ = ["DigitalTwinService"]
