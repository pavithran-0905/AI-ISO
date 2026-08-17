"""The regression sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

For every (suite, metric) pair with an established baseline, compares
its own latest result against that baseline. A regression beyond the
warning threshold creates a ``performance_regressions`` row, publishes
``RegressionDetected`` (fanned into the Performance Regression
notification -- see ``app.services.notifications``), and generates an
optimization recommendation for it. An improvement beyond the
improvement threshold publishes ``PerformanceImproved`` with no row of
its own, since docs/078's own DATABASE TABLES section has no
improvement-tracking table.

**Edge-triggered via the latest result's own ``created_at``
timestamp**, the same lookback-window shape every other edge-triggered
worker in this codebase uses, so a metric stuck below its baseline
does not re-notify on every tick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.domain_events import PerformanceImprovedEvent
from app.optimization.engine import category_for_regression
from app.regression.engine import (
    infer_regression_type,
    is_improvement,
    is_regression,
    regression_magnitude_percent,
)
from app.services.bundle import build_repositories
from app.services.notifications import BenchmarkNotifier
from app.services.optimization import OptimizationRecommendationService
from app.services.regressions import PerformanceRegressionService
from app.types import EventPublisher

logger = get_logger("app.workers.regression_sweep")

_SOURCE_SERVICE = "performance-benchmark-framework"


class RegressionSweepWorker:
    """Detects newly-regressed and newly-improved metrics against their
    own baselines."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher,
        notifier: BenchmarkNotifier,
        warning_threshold_percent: float,
        critical_threshold_percent: float,
        improvement_threshold_percent: float,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._notifier = notifier
        self._warning_threshold_percent = warning_threshold_percent
        self._critical_threshold_percent = critical_threshold_percent
        self._improvement_threshold_percent = improvement_threshold_percent
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Detect newly-regressed metrics across every organization,
        returning how many regressions were recorded."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        detected = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            regression_service = PerformanceRegressionService(
                repos.performance_regressions, publish=self._publish
            )
            optimization_service = OptimizationRecommendationService(
                repos.optimization_recommendations, publish=self._publish, notifier=self._notifier
            )

            for organization_id in await repos.benchmark_results.list_organization_ids():
                pairs = await repos.benchmark_results.list_distinct_suite_metric_pairs(
                    organization_id
                )
                for benchmark_suite_id, metric_name in pairs:
                    baseline = await repos.benchmark_baselines.find_by_suite_metric(
                        organization_id,
                        benchmark_suite_id=benchmark_suite_id,
                        metric_name=metric_name,
                    )
                    if baseline is None or not baseline.is_enabled:
                        continue

                    latest = await repos.benchmark_results.list_latest_by_suite_metric(
                        organization_id,
                        benchmark_suite_id=benchmark_suite_id,
                        metric_name=metric_name,
                        limit=1,
                    )
                    if not latest:
                        continue
                    result = latest[0]
                    if result.created_at < lookback_cutoff:
                        continue

                    if is_regression(
                        baseline=baseline.baseline_value,
                        current=result.value,
                        higher_is_better=baseline.higher_is_better,
                        warning_threshold_percent=self._warning_threshold_percent,
                    ):
                        suite = await repos.benchmark_suites.require_by_id(benchmark_suite_id)
                        regression_type = infer_regression_type(
                            metric_name=metric_name, benchmark_type=suite.benchmark_type
                        )
                        magnitude = regression_magnitude_percent(
                            baseline=baseline.baseline_value,
                            current=result.value,
                            higher_is_better=baseline.higher_is_better,
                        )
                        await regression_service.record(
                            organization_id,
                            regression_type=regression_type,
                            metric_name=metric_name,
                            baseline_value=baseline.baseline_value,
                            current_value=result.value,
                            regression_percent=magnitude,
                            critical_threshold_percent=self._critical_threshold_percent,
                        )
                        await optimization_service.create(
                            organization_id,
                            category=category_for_regression(regression_type),
                            title=f"Investigate {metric_name} regression in {suite.name}",
                            detail=(
                                f"{metric_name} regressed {magnitude:.1f}% against its own "
                                f"baseline ({baseline.baseline_value:.2f} -> {result.value:.2f})."
                            ),
                            magnitude_percent=magnitude,
                        )
                        detected += 1
                    elif is_improvement(
                        baseline=baseline.baseline_value,
                        current=result.value,
                        higher_is_better=baseline.higher_is_better,
                        improvement_threshold_percent=self._improvement_threshold_percent,
                    ):
                        await self._publish(
                            PerformanceImprovedEvent(
                                source_service=_SOURCE_SERVICE,
                                organization_id=organization_id,
                                payload={
                                    "metric_name": metric_name,
                                    "benchmark_suite_id": str(benchmark_suite_id),
                                },
                            )
                        )
            await session.commit()

        logger.info("regression sweep completed", extra={"extra_fields": {"detected": detected}})
        return detected


__all__ = ["RegressionSweepWorker"]
