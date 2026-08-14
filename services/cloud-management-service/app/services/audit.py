"""Audit recording: the one write path onto the immutable trail.

Every other service in this module calls through here rather than
constructing :class:`~app.models.reporting.CloudAudit` rows directly, so
the trail's shape cannot drift between call sites -- docs/068's own
AUDIT section requires account registration, provisioning, policy
changes, cost changes, IaC deployments, compliance changes, and
administrative operations all to be recorded, and a second, slightly
different construction path is how one of those quietly stops being
recorded.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import AuditAction
from app.models.reporting import CloudAudit
from app.repositories.reporting import CloudAuditRepository


class AuditService:
    """Records entries on the immutable cloud fleet audit trail."""

    def __init__(self, repo: CloudAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        action: AuditAction,
        entity_type: str,
        entity_id: UUID | None,
        occurred_at: datetime,
        actor_id: str | None = None,
        entity_reference: str | None = None,
        summary: str | None = None,
        succeeded: bool = True,
        details: dict[str, object] | None = None,
    ) -> CloudAudit:
        return await self._repo.create(
            CloudAudit(
                organization_id=organization_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_reference=entity_reference,
                occurred_at=occurred_at,
                actor_id=actor_id,
                summary=summary,
                succeeded=succeeded,
                details=details or {},
            )
        )


__all__ = ["AuditService"]
