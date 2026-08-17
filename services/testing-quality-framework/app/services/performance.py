"""Performance result and benchmark result recording.

Notifies Performance Regression / Benchmark Regression directly when
the newly-recorded measurement regresses against its own baseline.
"""

from __future__ import annotations

from uuid import UUID

from app.benchmark.engine import is_benchmark_regression
from app.events.domain_events import BenchmarkCompletedEvent
from app.models.enums import PerformanceTestType
from app.models.performance import BenchmarkResult, PerformanceResult
from app.performance.engine import is_performance_regression
from app.repositories.performance import BenchmarkResultRepository, PerformanceResultRepository
from app.services.notifications import QaNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "testing-quality-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PerformanceService:
    def __init__(
        self, repo: PerformanceResultRepository, *, notifier: QaNotifier | None = None
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def record(
        self,
        organization_id: UUID,
        *,
        performance_type: PerformanceTestType,
        latency_ms: float,
        throughput_rps: float = 0.0,
        baseline_latency_ms: float | None = None,
        tolerance_percent: float = 10.0,
        test_run_id: UUID | None = None,
        detail: str = "",
    ) -> PerformanceResult:
        result = await self._repo.create(
            PerformanceResult(
                organization_id=organization_id,
                test_run_id=test_run_id,
                performance_type=performance_type,
                latency_ms=latency_ms,
                throughput_rps=throughput_rps,
                detail=detail,
            )
        )
        if (
            baseline_latency_ms is not None
            and is_performance_regression(
                baseline=baseline_latency_ms,
                measured=latency_ms,
                tolerance_percent=tolerance_percent,
            )
            and self._notifier is not None
        ):
            await self._notifier.notify_performance_regression(
                performance_type=performance_type.value,
                detail=f"latency {latency_ms}ms vs baseline {baseline_latency_ms}ms",
            )
        return result


class BenchmarkService:
    def __init__(
        self,
        repo: BenchmarkResultRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: QaNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def record(
        self,
        organization_id: UUID,
        *,
        name: str,
        baseline_value: float,
        measured_value: float,
        unit: str = "",
        tolerance_percent: float = 10.0,
        higher_is_better: bool = True,
        detail: str = "",
    ) -> BenchmarkResult:
        result = await self._repo.create(
            BenchmarkResult(
                organization_id=organization_id,
                name=name,
                baseline_value=baseline_value,
                measured_value=measured_value,
                unit=unit,
                detail=detail,
            )
        )
        await self._publish(
            BenchmarkCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"benchmark_result_id": str(result.id), "name": name},
            )
        )
        if (
            is_benchmark_regression(
                baseline=baseline_value,
                measured=measured_value,
                tolerance_percent=tolerance_percent,
                higher_is_better=higher_is_better,
            )
            and self._notifier is not None
        ):
            await self._notifier.notify_benchmark_regression(
                benchmark_name=name, detail=f"{baseline_value}{unit} -> {measured_value}{unit}"
            )
        return result


__all__ = ["BenchmarkService", "PerformanceService"]
