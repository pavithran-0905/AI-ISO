"""The immutable developer portal audit trail.

**Single write path.** Every audit-worthy action across this service
-- documentation changes, plugin publications, administrative actions,
portal configuration, community moderation, knowledge updates -- routes
through :meth:`AuditService.record`, never a direct
``PortalAuditRepository`` call from anywhere else.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.enums import PortalAuditAction
from app.models.reporting import PortalAudit
from app.repositories.reporting import PortalAuditRepository


class AuditService:
    def __init__(self, repo: PortalAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        organization_id: UUID,
        action: PortalAuditAction,
        entity_type: str,
        entity_id: UUID,
        summary: str,
        occurred_at: datetime,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> PortalAudit:
        return await self._repo.create(
            PortalAudit(
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
    ) -> Sequence[PortalAudit]:
        return await self._repo.list_recent(organization_id, since=since, limit=limit)


__all__ = ["AuditService"]
