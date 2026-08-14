"""Cross-cluster distribution planning.

Wires ``app.federation.engine``'s pure distribution planning onto the
audit trail -- a federation plan is not itself a persisted domain
object in this build (no live cluster-to-cluster channel exists to
execute it over; see this service's README for the declared scope
boundary), but the *decision* of what would be distributed where is
still worth recording.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.federation.engine import DistributionPlan, plan_distribution
from app.models.enums import AuditAction
from app.services.audit import AuditService


class FederationService:
    def __init__(self, audit: AuditService) -> None:
        self._audit = audit

    async def plan(
        self,
        organization_id: UUID,
        *,
        source_cluster_id: UUID,
        requested_target_ids: list[UUID],
        resource_kind: str,
        actor_id: str | None,
        now: datetime,
    ) -> DistributionPlan:
        result = plan_distribution(source_cluster_id, requested_target_ids)
        await self._audit.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="federation_plan",
            entity_id=source_cluster_id,
            occurred_at=now,
            actor_id=actor_id,
            summary=(
                f"Planned {resource_kind} distribution from {source_cluster_id!s} to "
                f"{len(result.target_cluster_ids)} cluster(s)."
                if result.is_planned
                else f"Federation plan refused: {result.detail}"
            ),
            succeeded=result.is_planned,
        )
        return result


__all__ = ["FederationService"]
