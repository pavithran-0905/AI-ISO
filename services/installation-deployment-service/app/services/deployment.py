"""Deployment profiles, targets, jobs, the status board, versions, and
artifacts.

``DeploymentJobService`` is the one generic job engine shared by every
job type this service runs (install, deploy, upgrade, rollback) --
publishing ``DeploymentStarted``/``DeploymentCompleted`` on every job
regardless of type. ``UpgradeService`` and ``RollbackService`` (see
their own modules) build on top of it for their own more specific
``UpgradeStarted``/``UpgradeCompleted`` and
``RollbackStarted``/``RollbackCompleted`` events; a plain
``deploy``-type job has no more specific event pair of its own, so
``DeploymentStarted``/``DeploymentCompleted`` *is* its specific pair.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.deployment.engine import TransitionResult, validate_transition
from app.events.domain_events import DeploymentCompletedEvent, DeploymentStartedEvent
from app.models.deployment import (
    DeploymentArtifact,
    DeploymentHistory,
    DeploymentJob,
    DeploymentProfile,
    DeploymentStatusRecord,
    DeploymentTarget,
    DeploymentVersion,
)
from app.models.enums import (
    DeploymentEngine,
    DeploymentJobStatus,
    DeploymentJobType,
    DeploymentStrategy,
    DeploymentTargetType,
    InstallationMode,
    InventoryNodeStatus,
)
from app.repositories.deployment import (
    DeploymentArtifactRepository,
    DeploymentHistoryRepository,
    DeploymentJobRepository,
    DeploymentProfileRepository,
    DeploymentStatusRepository,
    DeploymentTargetRepository,
    DeploymentVersionRepository,
)
from app.services.notifications import DeploymentNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "installation-deployment-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class DeploymentProfileService:
    def __init__(self, repo: DeploymentProfileRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        target_type: DeploymentTargetType,
        installation_mode: InstallationMode,
        engine: DeploymentEngine,
        strategy: DeploymentStrategy,
    ) -> DeploymentProfile:
        return await self._repo.create(
            DeploymentProfile(
                organization_id=organization_id,
                name=name,
                target_type=target_type,
                installation_mode=installation_mode,
                engine=engine,
                strategy=strategy,
            )
        )


class DeploymentTargetService:
    def __init__(self, repo: DeploymentTargetRepository) -> None:
        self._repo = repo

    async def register(
        self,
        organization_id: UUID,
        *,
        deployment_profile_id: UUID,
        name: str,
        target_type: DeploymentTargetType,
        endpoint: str = "",
    ) -> DeploymentTarget:
        return await self._repo.create(
            DeploymentTarget(
                organization_id=organization_id,
                deployment_profile_id=deployment_profile_id,
                name=name,
                target_type=target_type,
                endpoint=endpoint,
            )
        )

    async def mark_status(
        self, target: DeploymentTarget, *, status: InventoryNodeStatus
    ) -> DeploymentTarget:
        target.status = status
        return await self._repo.update(target)


class DeploymentJobService:
    def __init__(
        self,
        repo: DeploymentJobRepository,
        history_repo: DeploymentHistoryRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: DeploymentNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._history_repo = history_repo
        self._publish = publish
        self._notifier = notifier

    async def create(
        self, organization_id: UUID, *, deployment_profile_id: UUID, job_type: DeploymentJobType
    ) -> DeploymentJob:
        return await self._repo.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=deployment_profile_id,
                job_type=job_type,
            )
        )

    async def start(self, job: DeploymentJob, *, now: datetime) -> DeploymentJob:
        result = validate_transition(job.status, DeploymentJobStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        job.status = DeploymentJobStatus.RUNNING
        job.started_at = now
        await self._repo.update(job)
        await self._history_repo.create(
            DeploymentHistory(
                organization_id=job.organization_id,
                deployment_job_id=job.id,
                event_type="started",
                occurred_at=now,
            )
        )
        await self._publish(
            DeploymentStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={"deployment_job_id": str(job.id), "job_type": str(job.job_type)},
            )
        )
        return job

    async def complete(
        self,
        job: DeploymentJob,
        *,
        status: DeploymentJobStatus,
        now: datetime,
        error_message: str = "",
    ) -> DeploymentJob:
        result = validate_transition(job.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        job.status = status
        job.completed_at = now
        job.error_message = error_message
        await self._repo.update(job)
        await self._history_repo.create(
            DeploymentHistory(
                organization_id=job.organization_id,
                deployment_job_id=job.id,
                event_type=status.value,
                detail=error_message,
                occurred_at=now,
            )
        )
        await self._publish(
            DeploymentCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={"deployment_job_id": str(job.id), "status": status.value},
            )
        )
        if status == DeploymentJobStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_deployment_failed(
                job_type=str(job.job_type), reason=error_message or "unspecified failure"
            )
        return job


class DeploymentStatusService:
    def __init__(self, repo: DeploymentStatusRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        deployment_target_id: UUID,
        status: DeploymentJobStatus,
        deployment_job_id: UUID | None = None,
        detail: str = "",
        now: datetime,
    ) -> DeploymentStatusRecord:
        """Upsert the current status board row for *deployment_target_id*."""
        existing = await self._repo.find_for_target(
            organization_id, deployment_target_id=deployment_target_id
        )
        if existing is not None:
            existing.status = status
            existing.deployment_job_id = deployment_job_id
            existing.detail = detail
            existing.updated_at_status = now
            return await self._repo.update(existing)
        return await self._repo.create(
            DeploymentStatusRecord(
                organization_id=organization_id,
                deployment_target_id=deployment_target_id,
                deployment_job_id=deployment_job_id,
                status=status,
                detail=detail,
                updated_at_status=now,
            )
        )


class DeploymentVersionService:
    def __init__(self, repo: DeploymentVersionRepository) -> None:
        self._repo = repo

    async def register(
        self, organization_id: UUID, *, version_label: str, released_at: datetime
    ) -> DeploymentVersion:
        return await self._repo.create(
            DeploymentVersion(
                organization_id=organization_id,
                version_label=version_label,
                released_at=released_at,
            )
        )

    async def mark_current(self, version: DeploymentVersion) -> DeploymentVersion:
        current = await self._repo.find_current(version.organization_id)
        if current is not None and current.id != version.id:
            current.is_current = False
            await self._repo.update(current)
        version.is_current = True
        return await self._repo.update(version)


class DeploymentArtifactService:
    def __init__(self, repo: DeploymentArtifactRepository) -> None:
        self._repo = repo

    async def register(
        self,
        organization_id: UUID,
        *,
        deployment_version_id: UUID,
        artifact_type: str,
        checksum_sha256: str,
        storage_ref: str = "",
    ) -> DeploymentArtifact:
        return await self._repo.create(
            DeploymentArtifact(
                organization_id=organization_id,
                deployment_version_id=deployment_version_id,
                artifact_type=artifact_type,
                checksum_sha256=checksum_sha256,
                storage_ref=storage_ref,
            )
        )


__all__ = [
    "DeploymentArtifactService",
    "DeploymentJobService",
    "DeploymentProfileService",
    "DeploymentStatusService",
    "DeploymentTargetService",
    "DeploymentVersionService",
    "TransitionRefusedError",
]
