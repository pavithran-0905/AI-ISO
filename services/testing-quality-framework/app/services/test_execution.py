"""Test run orchestration and per-case result recording.

Publishes ``TestStarted`` on a run's own start, and ``TestCompleted``
or ``TestFailed`` -- docs/077 names these as two distinct events, the
same shape ``services/upgrade-framework-service``'s own
``UpgradeCompleted``/``UpgradeFailed`` pair took (Prompt 076) -- on
completion.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import TestCompletedEvent, TestFailedEvent, TestStartedEvent
from app.models.enums import TestResultStatus, TestRunStatus
from app.models.test_execution import TestResult, TestRun
from app.pipeline.engine import TransitionResult, validate_transition
from app.repositories.test_execution import TestResultRepository, TestRunRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "testing-quality-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class TestRunService:
    def __init__(
        self, repo: TestRunRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create(
        self, organization_id: UUID, *, test_suite_id: UUID, test_environment_id: UUID | None = None
    ) -> TestRun:
        return await self._repo.create(
            TestRun(
                organization_id=organization_id,
                test_suite_id=test_suite_id,
                test_environment_id=test_environment_id,
            )
        )

    async def start(self, run: TestRun, *, now: datetime) -> TestRun:
        result = validate_transition(run.status, TestRunStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        run.status = TestRunStatus.RUNNING
        run.started_at = now
        await self._repo.update(run)
        await self._publish(
            TestStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=run.organization_id,
                payload={"test_run_id": str(run.id), "test_suite_id": str(run.test_suite_id)},
            )
        )
        return run

    async def complete(
        self, run: TestRun, *, status: TestRunStatus, now: datetime, error_message: str = ""
    ) -> TestRun:
        result = validate_transition(run.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        run.status = status
        run.completed_at = now
        run.error_message = error_message
        await self._repo.update(run)
        if status == TestRunStatus.SUCCEEDED:
            await self._publish(
                TestCompletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=run.organization_id,
                    payload={"test_run_id": str(run.id)},
                )
            )
        else:
            await self._publish(
                TestFailedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=run.organization_id,
                    payload={"test_run_id": str(run.id), "error_message": error_message},
                )
            )
        return run


class TestResultService:
    def __init__(self, repo: TestResultRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        test_run_id: UUID,
        test_case_id: UUID,
        status: TestResultStatus,
        duration_ms: int = 0,
        detail: str = "",
    ) -> TestResult:
        return await self._repo.create(
            TestResult(
                organization_id=organization_id,
                test_run_id=test_run_id,
                test_case_id=test_case_id,
                status=status,
                duration_ms=duration_ms,
                detail=detail,
            )
        )


__all__ = ["TestResultService", "TestRunService", "TransitionRefusedError"]
