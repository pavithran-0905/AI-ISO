"""Compliance assessment recording.

Wires ``app.compliance.engine``'s pure score classification and
remediation-due computation onto the repository that persists
assessments, and publishes ``ComplianceUpdated``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.compliance.engine import classify_compliance_score, compute_remediation_due
from app.events.domain_events import ComplianceUpdatedEvent
from app.models.enums import AuditAction, ClusterComplianceStatus, ComplianceFramework
from app.models.operations import ClusterCompliance
from app.repositories.operations import ClusterComplianceRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "multi-cluster-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class ComplianceService:
    def __init__(
        self,
        repo: ClusterComplianceRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def record_assessment(
        self,
        organization_id: UUID,
        *,
        cluster_id: UUID,
        framework: ComplianceFramework,
        score: float | None,
        findings: list[dict[str, object]],
        compliant_threshold: float,
        partial_threshold: float,
        grace_days: int,
        actor_id: str | None,
        now: datetime,
    ) -> ClusterCompliance:
        status = classify_compliance_score(
            score, compliant_threshold=compliant_threshold, partial_threshold=partial_threshold
        )
        remediation_due_at = (
            compute_remediation_due(now, grace_days=grace_days)
            if status is not ClusterComplianceStatus.COMPLIANT
            and status is not ClusterComplianceStatus.NOT_ASSESSED
            else None
        )
        assessment = await self._repo.create(
            ClusterCompliance(
                organization_id=organization_id,
                cluster_id=cluster_id,
                framework=framework,
                status=status,
                score=score,
                findings=findings,
                assessed_at=now,
                remediation_due_at=remediation_due_at,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.COMPLIANCE_CHANGED,
                entity_type="cluster_compliance",
                entity_id=assessment.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Assessed cluster {cluster_id!s} against {framework.value}: "
                f"{status.value}.",
            )
        await self._publish(
            ComplianceUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "cluster_id": str(cluster_id),
                    "framework": str(framework),
                    "status": str(status),
                    "score": score,
                },
            )
        )
        return assessment


__all__ = ["ComplianceService"]
