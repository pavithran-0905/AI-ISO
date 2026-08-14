"""The immutable mobile audit trail.

**Single write path.** Every audit-worthy action across this service
-- device registration, authentication, configuration changes,
synchronization, administrative operations -- routes through
:meth:`AuditService.record`, never a direct ``MobileAuditRepository``
call from anywhere else. One write path is the only way "every action
is audited" stays true as the service grows.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.enums import MobileAuditAction
from app.models.reporting import MobileAudit
from app.repositories.reporting import MobileAuditRepository


class AuditService:
    def __init__(self, repo: MobileAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        organization_id: UUID,
        action: MobileAuditAction,
        entity_type: str,
        entity_id: UUID,
        summary: str,
        occurred_at: datetime,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> MobileAudit:
        return await self._repo.create(
            MobileAudit(
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
    ) -> Sequence[MobileAudit]:
        return await self._repo.list_recent(organization_id, since=since, limit=limit)


__all__ = ["AuditService"]
