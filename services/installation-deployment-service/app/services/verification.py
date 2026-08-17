"""Post-install/post-upgrade verification.

Like preflight, this is a caller-reported-outcome service: the checks
this process can perform for real (database, cache) are recorded
alongside checks a deployed workload's own health probe reports back
(API, authentication, plugin, performance, smoke test)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ValidationCompletedEvent
from app.models.enums import CheckResultStatus, VerificationCheckType
from app.models.verification import VerificationResult
from app.repositories.verification import VerificationResultRepository
from app.services.notifications import DeploymentNotifier
from app.types import EventPublisher
from app.verification.engine import compute_verification_outcome

_SOURCE_SERVICE = "installation-deployment-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class VerificationService:
    def __init__(
        self,
        repo: VerificationResultRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: DeploymentNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def record_result(
        self,
        organization_id: UUID,
        *,
        check_type: VerificationCheckType,
        status: CheckResultStatus,
        detail: str = "",
        deployment_job_id: UUID | None = None,
        now: datetime,
    ) -> VerificationResult:
        result = await self._repo.create(
            VerificationResult(
                organization_id=organization_id,
                deployment_job_id=deployment_job_id,
                check_type=check_type,
                status=status,
                detail=detail,
                verified_at=now,
            )
        )
        await self._publish(
            ValidationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"check_type": check_type.value, "status": status.value},
            )
        )
        if status == CheckResultStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_validation_failed(
                check_type=check_type.value, detail=detail
            )
        return result

    async def compute_overall(self, deployment_job_id: UUID) -> CheckResultStatus:
        results = await self._repo.list_for_job(deployment_job_id)
        return compute_verification_outcome(CheckResultStatus(result.status) for result in results)


__all__ = ["VerificationService"]
