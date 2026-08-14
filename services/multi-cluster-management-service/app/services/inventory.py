"""Cluster resource inventory recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.operations import ClusterInventory
from app.repositories.operations import ClusterInventoryRepository


class InventoryService:
    def __init__(self, repo: ClusterInventoryRepository) -> None:
        self._repo = repo

    async def record_snapshot(
        self,
        organization_id: UUID,
        *,
        cluster_id: UUID,
        resource_kind: str,
        resource_count: int,
        details: dict[str, object],
        collected_at: datetime,
    ) -> ClusterInventory:
        return await self._repo.create(
            ClusterInventory(
                organization_id=organization_id,
                cluster_id=cluster_id,
                resource_kind=resource_kind,
                resource_count=resource_count,
                details=details,
                collected_at=collected_at,
            )
        )


__all__ = ["InventoryService"]
