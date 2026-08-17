"""Hardening run orchestration and per-check result recording.

Publishes ``HardeningStarted`` on a run's own start, and
``HardeningCompleted`` on every terminal state -- docs/079 names one
completion event covering both outcomes, the same shape
``services/performance-benchmark-framework``'s own
``BenchmarkCompleted`` uses (Prompt 078).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import HardeningCompletedEvent, HardeningStartedEvent
from app.hardening.engine import TransitionResult, validate_transition
from app.models.enums import CheckResultStatus, HardeningRunStatus
from app.models.hardening_execution import HardeningResult, HardeningRun
from app.repositories.hardening_execution import HardeningResultRepository, HardeningRunRepository
from app.services.notifications import HardeningNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "production-hardening-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class HardeningRunService:
    def __init__(
        self,
        repo: HardeningRunRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: HardeningNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def create(self, organization_id: UUID, *, hardening_profile_id: UUID) -> HardeningRun:
        return await self._repo.create(
            HardeningRun(organization_id=organization_id, hardening_profile_id=hardening_profile_id)
        )

    async def start(self, run: HardeningRun, *, now: datetime) -> HardeningRun:
        result = validate_transition(run.status, HardeningRunStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        run.status = HardeningRunStatus.RUNNING
        run.started_at = now
        await self._repo.update(run)
        await self._publish(
            HardeningStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=run.organization_id,
                payload={
                    "hardening_run_id": str(run.id),
                    "hardening_profile_id": str(run.hardening_profile_id),
                },
            )
        )
        return run

    async def complete(
        self,
        run: HardeningRun,
        *,
        status: HardeningRunStatus,
        now: datetime,
        error_message: str = "",
        hardening_profile_name: str = "",
    ) -> HardeningRun:
        result = validate_transition(run.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        run.status = status
        run.completed_at = now
        run.error_message = error_message
        run = await self._repo.update(run)
        await self._publish(
            HardeningCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=run.organization_id,
                payload={"hardening_run_id": str(run.id), "status": str(status)},
            )
        )
        if self._notifier is not None and status == HardeningRunStatus.FAILED:
            await self._notifier.notify_hardening_failed(
                hardening_profile_name=hardening_profile_name, error_message=error_message
            )
        return run


class HardeningResultService:
    def __init__(self, repo: HardeningResultRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        hardening_run_id: UUID,
        check_name: str,
        status: CheckResultStatus,
        detail: str = "",
    ) -> HardeningResult:
        return await self._repo.create(
            HardeningResult(
                organization_id=organization_id,
                hardening_run_id=hardening_run_id,
                check_name=check_name,
                status=status,
                detail=detail,
            )
        )


__all__ = ["HardeningResultService", "HardeningRunService", "TransitionRefusedError"]
