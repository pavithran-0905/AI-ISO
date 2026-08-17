"""Upgrade plans and the jobs that execute them.

``UpgradeJobService`` is the low-level, event-free job engine shared
by both this module's own ``UpgradeExecutionService`` (which adds the
``UpgradeScheduled``/``UpgradeStarted``/``UpgradeCompleted``/
``UpgradeFailed`` events) and ``app.services.rollback.RollbackService``
(which adds its own ``RollbackStarted``/``RollbackCompleted`` events
instead) -- one shared status-transition engine, two different event
vocabularies layered on top, since docs/076 names upgrade events and
rollback events as entirely separate pairs rather than one generic
"job" pair the way ``services/installation-deployment-service``'s own
``DeploymentJobService`` did (Prompt 075).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import (
    UpgradeCompletedEvent,
    UpgradeFailedEvent,
    UpgradeScheduledEvent,
    UpgradeStartedEvent,
)
from app.models.enums import UpgradeJobStatus, UpgradeStrategy, UpgradeTargetType
from app.models.upgrade import UpgradeHistory, UpgradeJob, UpgradePlan
from app.repositories.upgrade import (
    UpgradeHistoryRepository,
    UpgradeJobRepository,
    UpgradePlanRepository,
)
from app.services.notifications import UpgradeNotifier
from app.types import EventPublisher
from app.upgrade.engine import TransitionResult, validate_transition

_SOURCE_SERVICE = "upgrade-framework-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class UpgradePlanService:
    def __init__(self, repo: UpgradePlanRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        target_type: UpgradeTargetType,
        strategy: UpgradeStrategy,
        from_version: str,
        to_version: str,
        release_channel_id: UUID | None = None,
    ) -> UpgradePlan:
        return await self._repo.create(
            UpgradePlan(
                organization_id=organization_id,
                name=name,
                target_type=target_type,
                strategy=strategy,
                from_version=from_version,
                to_version=to_version,
                release_channel_id=release_channel_id,
            )
        )


class UpgradeJobService:
    """The shared, event-free job engine: status transitions plus
    append-only history, nothing more. Every specific event vocabulary
    is layered on top by a calling service."""

    def __init__(self, repo: UpgradeJobRepository, history_repo: UpgradeHistoryRepository) -> None:
        self._repo = repo
        self._history_repo = history_repo

    async def create(self, organization_id: UUID, *, upgrade_plan_id: UUID) -> UpgradeJob:
        return await self._repo.create(
            UpgradeJob(organization_id=organization_id, upgrade_plan_id=upgrade_plan_id)
        )

    async def start(self, job: UpgradeJob, *, now: datetime) -> UpgradeJob:
        result = validate_transition(job.status, UpgradeJobStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        job.status = UpgradeJobStatus.RUNNING
        job.started_at = now
        await self._repo.update(job)
        await self._history_repo.create(
            UpgradeHistory(
                organization_id=job.organization_id,
                upgrade_job_id=job.id,
                event_type="started",
                occurred_at=now,
            )
        )
        return job

    async def complete(
        self, job: UpgradeJob, *, status: UpgradeJobStatus, now: datetime, error_message: str = ""
    ) -> UpgradeJob:
        result = validate_transition(job.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        job.status = status
        job.completed_at = now
        job.error_message = error_message
        await self._repo.update(job)
        await self._history_repo.create(
            UpgradeHistory(
                organization_id=job.organization_id,
                upgrade_job_id=job.id,
                event_type=status.value,
                detail=error_message,
                occurred_at=now,
            )
        )
        return job


class UpgradeExecutionService:
    """The public-facing upgrade orchestrator: schedules and runs an
    upgrade job, adding docs/076's own upgrade-specific events and
    notifications on top of ``UpgradeJobService``'s bare state
    transitions."""

    def __init__(
        self,
        job_service: UpgradeJobService,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: UpgradeNotifier | None = None,
    ) -> None:
        self._job_service = job_service
        self._publish = publish
        self._notifier = notifier

    async def schedule_and_start(
        self, organization_id: UUID, *, upgrade_plan_id: UUID, plan_name: str, now: datetime
    ) -> UpgradeJob:
        job = await self._job_service.create(organization_id, upgrade_plan_id=upgrade_plan_id)
        await self._publish(
            UpgradeScheduledEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"upgrade_job_id": str(job.id), "upgrade_plan_id": str(upgrade_plan_id)},
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_upgrade_scheduled(plan_name=plan_name)

        job = await self._job_service.start(job, now=now)
        await self._publish(
            UpgradeStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"upgrade_job_id": str(job.id), "upgrade_plan_id": str(upgrade_plan_id)},
            )
        )
        return job

    async def complete(
        self, job: UpgradeJob, *, status: UpgradeJobStatus, now: datetime, error_message: str = ""
    ) -> UpgradeJob:
        job = await self._job_service.complete(
            job, status=status, now=now, error_message=error_message
        )
        if status == UpgradeJobStatus.SUCCEEDED:
            await self._publish(
                UpgradeCompletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=job.organization_id,
                    payload={"upgrade_job_id": str(job.id)},
                )
            )
        else:
            await self._publish(
                UpgradeFailedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=job.organization_id,
                    payload={"upgrade_job_id": str(job.id), "error_message": error_message},
                )
            )
            if self._notifier is not None:
                await self._notifier.notify_upgrade_failed(
                    reason=error_message or "unspecified failure"
                )
        return job


__all__ = [
    "TransitionRefusedError",
    "UpgradeExecutionService",
    "UpgradeJobService",
    "UpgradePlanService",
]
