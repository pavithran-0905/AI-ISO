"""The immutable developer platform audit trail.

**Single write path.** Every audit-worthy action across this service
-- developer registration, application changes, credential changes,
API publication, version releases, administrative operations -- routes
through :meth:`AuditService.record`, never a direct
``DeveloperAuditRepository`` call from anywhere else.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.enums import DeveloperAuditAction
from app.models.reporting import DeveloperAudit
from app.repositories.reporting import DeveloperAuditRepository


class AuditService:
    def __init__(self, repo: DeveloperAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        organization_id: UUID,
        action: DeveloperAuditAction,
        entity_type: str,
        entity_id: UUID,
        summary: str,
        occurred_at: datetime,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> DeveloperAudit:
        return await self._repo.create(
            DeveloperAudit(
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
    ) -> Sequence[DeveloperAudit]:
        return await self._repo.list_recent(organization_id, since=since, limit=limit)


__all__ = ["AuditService"]
