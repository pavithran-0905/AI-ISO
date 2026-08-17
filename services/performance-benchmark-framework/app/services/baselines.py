"""Benchmark baseline selection.

**Automatic Baseline Selection** (docs/078's own BASELINES section):
the first result ever recorded for a (suite, metric) pair becomes that
metric's baseline, with no separate admin step required -- see
:meth:`BenchmarkBaselineService.get_or_create_initial`, called by
``BenchmarkResultService.record``.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import BaselineUpdatedEvent
from app.models.baselines import BenchmarkBaseline
from app.repositories.baselines import BenchmarkBaselineRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "performance-benchmark-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class BenchmarkBaselineService:
    def __init__(
        self, repo: BenchmarkBaselineRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def get_or_create_initial(
        self,
        organization_id: UUID,
        *,
        benchmark_suite_id: UUID,
        metric_name: str,
        value: float,
        unit: str,
        higher_is_better: bool,
    ) -> BenchmarkBaseline:
        """Return the existing baseline for this (suite, metric) pair, or
        automatically create one from *value* if none exists yet."""
        existing = await self._repo.find_by_suite_metric(
            organization_id, benchmark_suite_id=benchmark_suite_id, metric_name=metric_name
        )
        if existing is not None:
            return existing
        return await self.set_baseline(
            organization_id,
            benchmark_suite_id=benchmark_suite_id,
            metric_name=metric_name,
            baseline_value=value,
            unit=unit,
            higher_is_better=higher_is_better,
        )

    async def set_baseline(
        self,
        organization_id: UUID,
        *,
        benchmark_suite_id: UUID,
        metric_name: str,
        baseline_value: float,
        unit: str,
        higher_is_better: bool,
    ) -> BenchmarkBaseline:
        """Explicitly set (or replace) a (suite, metric) pair's own
        baseline."""
        existing = await self._repo.find_by_suite_metric(
            organization_id, benchmark_suite_id=benchmark_suite_id, metric_name=metric_name
        )
        if existing is not None:
            existing.baseline_value = baseline_value
            existing.unit = unit
            existing.higher_is_better = higher_is_better
            baseline = await self._repo.update(existing)
        else:
            baseline = await self._repo.create(
                BenchmarkBaseline(
                    organization_id=organization_id,
                    benchmark_suite_id=benchmark_suite_id,
                    metric_name=metric_name,
                    baseline_value=baseline_value,
                    unit=unit,
                    higher_is_better=higher_is_better,
                )
            )
        await self._publish(
            BaselineUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"benchmark_baseline_id": str(baseline.id), "metric_name": metric_name},
            )
        )
        return baseline


__all__ = ["BenchmarkBaselineService"]
