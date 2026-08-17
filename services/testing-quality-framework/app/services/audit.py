"""The immutable QA audit trail.

**Single write path.** Every audit-worthy action across this service
-- test execution, quality gate changes, security scan results,
pipeline approvals, administrative actions -- routes through
:meth:`AuditService.record`, never a direct ``QaAuditRepository`` call
from anywhere else.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.enums import QaAuditAction
from app.models.reporting import QaAudit
from app.repositories.reporting import QaAuditRepository


class AuditService:
    def __init__(self, repo: QaAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        organization_id: UUID,
        action: QaAuditAction,
        entity_type: str,
        entity_id: UUID,
        summary: str,
        occurred_at: datetime,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> QaAudit:
        return await self._repo.create(
            QaAudit(
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
    ) -> Sequence[QaAudit]:
        return await self._repo.list_recent(organization_id, since=since, limit=limit)


__all__ = ["AuditService"]
