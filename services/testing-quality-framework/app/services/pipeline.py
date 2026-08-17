"""Pipeline result orchestration.

Notifies Pipeline Failed directly on a pipeline's own failed
completion.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import TestRunStatus
from app.models.pipeline import PipelineResult
from app.pipeline.engine import TransitionResult, validate_transition
from app.repositories.pipeline import PipelineResultRepository
from app.services.notifications import QaNotifier


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class PipelineService:
    def __init__(
        self, repo: PipelineResultRepository, *, notifier: QaNotifier | None = None
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def start(self, organization_id: UUID, *, name: str, now: datetime) -> PipelineResult:
        return await self._repo.create(
            PipelineResult(
                organization_id=organization_id,
                name=name,
                status=TestRunStatus.RUNNING,
                started_at=now,
            )
        )

    async def complete(
        self, pipeline: PipelineResult, *, status: TestRunStatus, now: datetime, detail: str = ""
    ) -> PipelineResult:
        result = validate_transition(pipeline.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        pipeline.status = status
        pipeline.completed_at = now
        pipeline.detail = detail
        pipeline = await self._repo.update(pipeline)
        if status == TestRunStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_pipeline_failed(
                pipeline_name=pipeline.name, reason=detail or "unspecified failure"
            )
        return pipeline


__all__ = ["PipelineService", "TransitionRefusedError"]
