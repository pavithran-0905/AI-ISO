"""Compliance assessment recording.

Wires ``app.compliance.engine``'s pure score classification and
remediation scheduling onto the repository that persists assessments.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.compliance.engine import classify_compliance_status, compute_remediation_due_at
from app.models.enums import AuditAction, CloudComplianceFramework
from app.models.operations import CloudCompliance
from app.repositories.operations import CloudComplianceRepository
from app.services.audit import AuditService


class CloudComplianceService:
    def __init__(
        self, repo: CloudComplianceRepository, *, audit: AuditService | None = None
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def assess(
        self,
        organization_id: UUID,
        *,
        account_id: UUID,
        framework: CloudComplianceFramework,
        score: float | None,
        compliant_threshold: float,
        partial_threshold: float,
        remediation_grace_days: int,
        actor_id: str | None,
        now: datetime,
    ) -> CloudCompliance:
        status = classify_compliance_status(
            score, compliant_threshold=compliant_threshold, partial_threshold=partial_threshold
        )
        remediation_due_at = (
            compute_remediation_due_at(now, grace_days=remediation_grace_days)
            if status.value in ("partially_compliant", "non_compliant")
            else None
        )
        assessment = await self._repo.create(
            CloudCompliance(
                organization_id=organization_id,
                account_id=account_id,
                framework=framework,
                status=status,
                score=score,
                assessed_at=now,
                remediation_due_at=remediation_due_at,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.COMPLIANCE_CHANGED,
                entity_type="cloud_compliance",
                entity_id=assessment.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=(
                    f"Assessed account {account_id!s} against {framework.value}: {status.value}."
                ),
            )
        return assessment


__all__ = ["CloudComplianceService"]
