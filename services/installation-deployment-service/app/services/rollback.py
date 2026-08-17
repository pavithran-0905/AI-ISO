"""Platform rollback orchestration.

Builds on ``DeploymentJobService`` for the underlying job's own
generic lifecycle, adding the rollback-specific
``RollbackStarted``/``RollbackCompleted`` events, a
``rollback_history`` row, and version-path validation via
``app.rollback.engine``. ``RollbackCompleted`` is the one event this
service fans into a notification (Rollback Completed) via
``NotifyingPublisher``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from app.events.domain_events import RollbackCompletedEvent, RollbackStartedEvent
from app.models.deployment import DeploymentJob
from app.models.enums import DeploymentJobStatus, DeploymentJobType
from app.models.upgrade_rollback import RollbackHistory
from app.repositories.upgrade_rollback import RollbackHistoryRepository
from app.rollback.engine import can_rollback_to
from app.services.deployment import DeploymentJobService
from app.types import EventPublisher

_SOURCE_SERVICE = "installation-deployment-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class InvalidRollbackTargetError(Exception):
    def __init__(self, *, current_version: str, target_version: str) -> None:
        super().__init__(f"Cannot roll back from {current_version} to {target_version}.")
        self.current_version = current_version
        self.target_version = target_version


class RollbackService:
    def __init__(
        self,
        repo: RollbackHistoryRepository,
        job_service: DeploymentJobService,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._repo = repo
        self._job_service = job_service
        self._publish = publish

    async def initiate(
        self,
        organization_id: UUID,
        *,
        deployment_profile_id: UUID,
        current_version: str,
        target_version: str,
        available_versions: Iterable[str],
        reason: str = "",
        now: datetime,
    ) -> RollbackHistory:
        if not can_rollback_to(
            current_version=current_version,
            target_version=target_version,
            available_versions=available_versions,
        ):
            raise InvalidRollbackTargetError(
                current_version=current_version, target_version=target_version
            )

        job = await self._job_service.create(
            organization_id,
            deployment_profile_id=deployment_profile_id,
            job_type=DeploymentJobType.ROLLBACK,
        )
        await self._job_service.start(job, now=now)
        history = await self._repo.create(
            RollbackHistory(
                organization_id=organization_id,
                deployment_job_id=job.id,
                from_version=current_version,
                to_version=target_version,
                reason=reason,
                status=DeploymentJobStatus.RUNNING,
                started_at=now,
            )
        )
        await self._publish(
            RollbackStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "deployment_job_id": str(job.id),
                    "from_version": current_version,
                    "to_version": target_version,
                },
            )
        )
        return history

    async def complete(
        self,
        history: RollbackHistory,
        job: DeploymentJob,
        *,
        status: DeploymentJobStatus,
        now: datetime,
        error_message: str = "",
    ) -> RollbackHistory:
        await self._job_service.complete(job, status=status, now=now, error_message=error_message)
        history.status = status
        history.completed_at = now
        history = await self._repo.update(history)
        await self._publish(
            RollbackCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=history.organization_id,
                payload={
                    "deployment_job_id": str(history.deployment_job_id),
                    "status": status.value,
                    "to_version": history.to_version,
                },
            )
        )
        return history


__all__ = ["InvalidRollbackTargetError", "RollbackService"]
