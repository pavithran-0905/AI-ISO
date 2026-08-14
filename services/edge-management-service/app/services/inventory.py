"""Device inventory snapshot recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.devices import EdgeInventory
from app.repositories.devices import EdgeInventoryRepository


class InventoryService:
    def __init__(self, repo: EdgeInventoryRepository) -> None:
        self._repo = repo

    async def record_snapshot(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        resource_kind: str,
        resource_count: int,
        details: dict[str, object] | None,
        now: datetime,
    ) -> EdgeInventory:
        return await self._repo.create(
            EdgeInventory(
                organization_id=organization_id,
                device_id=device_id,
                resource_kind=resource_kind,
                resource_count=resource_count,
                collected_at=now,
                details=details or {},
            )
        )


__all__ = ["InventoryService"]
