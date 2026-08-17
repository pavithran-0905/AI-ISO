"""Platform upgrade orchestration.

Builds on ``DeploymentJobService`` for the underlying job's own
generic lifecycle, adding the upgrade-specific
``UpgradeStarted``/``UpgradeCompleted`` events, an ``upgrade_history``
row, and version-path validation via ``app.upgrade.engine``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import UpgradeCompletedEvent, UpgradeStartedEvent
from app.models.deployment import DeploymentJob
from app.models.enums import DeploymentJobStatus, DeploymentJobType
from app.models.upgrade_rollback import UpgradeHistory
from app.repositories.upgrade_rollback import UpgradeHistoryRepository
from app.services.deployment import DeploymentJobService
from app.services.notifications import DeploymentNotifier
from app.types import EventPublisher
from app.upgrade.engine import is_upgrade_path_valid

_SOURCE_SERVICE = "installation-deployment-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class InvalidUpgradePathError(Exception):
    def __init__(self, *, from_version: str, to_version: str) -> None:
        super().__init__(f"{from_version} -> {to_version} is not a valid upgrade path.")
        self.from_version = from_version
        self.to_version = to_version


class UpgradeService:
    def __init__(
        self,
        repo: UpgradeHistoryRepository,
        job_service: DeploymentJobService,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: DeploymentNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._job_service = job_service
        self._publish = publish
        self._notifier = notifier

    async def initiate(
        self,
        organization_id: UUID,
        *,
        deployment_profile_id: UUID,
        from_version: str,
        to_version: str,
        now: datetime,
    ) -> UpgradeHistory:
        if not is_upgrade_path_valid(from_version=from_version, to_version=to_version):
            raise InvalidUpgradePathError(from_version=from_version, to_version=to_version)

        job = await self._job_service.create(
            organization_id,
            deployment_profile_id=deployment_profile_id,
            job_type=DeploymentJobType.UPGRADE,
        )
        await self._job_service.start(job, now=now)
        history = await self._repo.create(
            UpgradeHistory(
                organization_id=organization_id,
                deployment_job_id=job.id,
                from_version=from_version,
                to_version=to_version,
                status=DeploymentJobStatus.RUNNING,
                started_at=now,
            )
        )
        await self._publish(
            UpgradeStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "deployment_job_id": str(job.id),
                    "from_version": from_version,
                    "to_version": to_version,
                },
            )
        )
        return history

    async def complete(
        self,
        history: UpgradeHistory,
        job: DeploymentJob,
        *,
        status: DeploymentJobStatus,
        now: datetime,
        error_message: str = "",
    ) -> UpgradeHistory:
        await self._job_service.complete(job, status=status, now=now, error_message=error_message)
        history.status = status
        history.completed_at = now
        history = await self._repo.update(history)
        await self._publish(
            UpgradeCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=history.organization_id,
                payload={
                    "deployment_job_id": str(history.deployment_job_id),
                    "status": status.value,
                },
            )
        )
        if status == DeploymentJobStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_upgrade_failed(
                to_version=history.to_version, reason=error_message or "unspecified failure"
            )
        return history


__all__ = ["InvalidUpgradePathError", "UpgradeService"]
