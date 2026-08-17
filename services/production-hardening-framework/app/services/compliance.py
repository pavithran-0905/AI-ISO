"""Compliance control evaluation.

Publishes ``ComplianceValidated`` on every evaluation, regardless of
outcome, and notifies Compliance Failure directly on a non-compliant
result -- the same "always publish, conditionally notify" shape
``services/testing-quality-framework``'s own ``QualityGateService``
uses (Prompt 077).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ComplianceValidatedEvent
from app.models.compliance import ComplianceResult
from app.models.enums import ComplianceFramework
from app.repositories.compliance import ComplianceResultRepository
from app.services.notifications import HardeningNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "production-hardening-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class ComplianceService:
    def __init__(
        self,
        repo: ComplianceResultRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: HardeningNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def evaluate(
        self,
        organization_id: UUID,
        *,
        framework: ComplianceFramework,
        control_id: str,
        is_compliant: bool,
        evaluated_at: datetime,
    ) -> ComplianceResult:
        result = await self._repo.create(
            ComplianceResult(
                organization_id=organization_id,
                framework=framework,
                control_id=control_id,
                is_compliant=is_compliant,
                evaluated_at=evaluated_at,
            )
        )
        await self._publish(
            ComplianceValidatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "compliance_result_id": str(result.id),
                    "framework": str(framework),
                    "is_compliant": is_compliant,
                },
            )
        )
        if self._notifier is not None and not is_compliant:
            await self._notifier.notify_compliance_failure(
                framework=str(framework), control_id=control_id
            )
        return result


__all__ = ["ComplianceService"]
