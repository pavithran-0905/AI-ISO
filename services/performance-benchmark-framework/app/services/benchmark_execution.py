"""Benchmark run orchestration and per-metric result recording.

Publishes ``BenchmarkStarted`` on a run's own start, and
``BenchmarkCompleted`` on every terminal state -- docs/078 names one
completion event covering both outcomes, unlike
``services/testing-quality-framework``'s own ``TestCompleted``/
``TestFailed`` pair (Prompt 077).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.benchmark.engine import TransitionResult, validate_transition
from app.events.domain_events import BenchmarkCompletedEvent, BenchmarkStartedEvent
from app.models.benchmark_execution import BenchmarkResult, BenchmarkRun
from app.models.enums import BenchmarkRunStatus
from app.repositories.benchmark_execution import BenchmarkResultRepository, BenchmarkRunRepository
from app.services.baselines import BenchmarkBaselineService
from app.services.notifications import BenchmarkNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "performance-benchmark-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class BenchmarkRunService:
    def __init__(
        self,
        repo: BenchmarkRunRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: BenchmarkNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def create(
        self,
        organization_id: UUID,
        *,
        benchmark_suite_id: UUID,
        benchmark_profile_id: UUID | None = None,
    ) -> BenchmarkRun:
        return await self._repo.create(
            BenchmarkRun(
                organization_id=organization_id,
                benchmark_suite_id=benchmark_suite_id,
                benchmark_profile_id=benchmark_profile_id,
            )
        )

    async def start(self, run: BenchmarkRun, *, now: datetime) -> BenchmarkRun:
        result = validate_transition(run.status, BenchmarkRunStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        run.status = BenchmarkRunStatus.RUNNING
        run.started_at = now
        await self._repo.update(run)
        await self._publish(
            BenchmarkStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=run.organization_id,
                payload={
                    "benchmark_run_id": str(run.id),
                    "benchmark_suite_id": str(run.benchmark_suite_id),
                },
            )
        )
        return run

    async def complete(
        self,
        run: BenchmarkRun,
        *,
        status: BenchmarkRunStatus,
        now: datetime,
        error_message: str = "",
        benchmark_suite_name: str = "",
    ) -> BenchmarkRun:
        result = validate_transition(run.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        run.status = status
        run.completed_at = now
        run.error_message = error_message
        run = await self._repo.update(run)
        await self._publish(
            BenchmarkCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=run.organization_id,
                payload={"benchmark_run_id": str(run.id), "status": str(status)},
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_benchmark_completed(
                benchmark_suite_name=benchmark_suite_name, status=str(status)
            )
        return run


class BenchmarkResultService:
    def __init__(
        self, repo: BenchmarkResultRepository, *, baselines: BenchmarkBaselineService
    ) -> None:
        self._repo = repo
        self._baselines = baselines

    async def record(
        self,
        organization_id: UUID,
        *,
        benchmark_run_id: UUID,
        benchmark_suite_id: UUID,
        metric_name: str,
        value: float,
        unit: str = "",
        higher_is_better: bool = True,
    ) -> BenchmarkResult:
        result = await self._repo.create(
            BenchmarkResult(
                organization_id=organization_id,
                benchmark_run_id=benchmark_run_id,
                metric_name=metric_name,
                value=value,
                unit=unit,
            )
        )
        await self._baselines.get_or_create_initial(
            organization_id,
            benchmark_suite_id=benchmark_suite_id,
            metric_name=metric_name,
            value=value,
            unit=unit,
            higher_is_better=higher_is_better,
        )
        return result


__all__ = ["BenchmarkResultService", "BenchmarkRunService", "TransitionRefusedError"]
