"""The immutable upgrade audit trail.

**Single write path.** Every audit-worthy action across this service
-- upgrade scheduling, upgrade execution, rollback operations,
migration execution, release publication, administrative actions --
routes through :meth:`AuditService.record`, never a direct
``UpgradeAuditRepository`` call from anywhere else.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.enums import UpgradeAuditAction
from app.models.reporting import UpgradeAudit
from app.repositories.reporting import UpgradeAuditRepository


class AuditService:
    def __init__(self, repo: UpgradeAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        organization_id: UUID,
        action: UpgradeAuditAction,
        entity_type: str,
        entity_id: UUID,
        summary: str,
        occurred_at: datetime,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> UpgradeAudit:
        return await self._repo.create(
            UpgradeAudit(
                organization_id=organization_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=actor_id,
                summary=summary,
                detail=detail or {},
                occurred_at=occurred_at,
            )
        )

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[UpgradeAudit]:
        return await self._repo.list_recent(organization_id, since=since, limit=limit)


__all__ = ["AuditService"]
