"""Infrastructure-as-Code deployment tracking.

Wires ``app.iac.engine``'s pure transition table onto the repository
that persists deployment tracking rows.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.iac.engine import TransitionResult, validate_transition
from app.models.enums import AuditAction, IaCDeploymentStatus, IaCTool
from app.models.operations import CloudIaC
from app.repositories.operations import CloudIaCRepository
from app.services.audit import AuditService


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class CloudIaCService:
    def __init__(self, repo: CloudIaCRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def plan(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID | None,
        tool: IaCTool,
        state_reference: str | None,
        version_label: str | None,
    ) -> CloudIaC:
        return await self._repo.create(
            CloudIaC(
                organization_id=organization_id,
                resource_id=resource_id,
                tool=tool,
                status=IaCDeploymentStatus.PLANNED,
                state_reference=state_reference,
                version_label=version_label,
            )
        )

    async def transition(
        self,
        deployment: CloudIaC,
        *,
        target: IaCDeploymentStatus,
        actor_id: str | None,
        now: datetime,
    ) -> CloudIaC:
        """Move *deployment* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(deployment.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        deployment.status = target
        if target == IaCDeploymentStatus.APPLIED:
            deployment.applied_at = now
        await self._repo.update(deployment)

        if self._audit is not None:
            await self._audit.record(
                deployment.organization_id,
                action=AuditAction.IAC_DEPLOYED,
                entity_type="cloud_iac",
                entity_id=deployment.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"IaC deployment {deployment.id!s} moved to {target.value}.",
            )
        return deployment


__all__ = ["CloudIaCService", "TransitionRefusedError"]
