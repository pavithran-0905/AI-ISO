"""The capacity threshold sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies Capacity Warning for any capacity model whose own latest
forecast has reached its threshold, publishes
``CapacityThresholdReached``, and generates a scaling optimization
recommendation. **Edge-triggered via the latest forecast's own
``created_at`` timestamp**, the same lookback-window shape every other
edge-triggered worker in this codebase uses, so a resource stuck past
its threshold does not re-notify on every tick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.capacity.engine import is_threshold_breached
from app.events.domain_events import CapacityThresholdReachedEvent
from app.models.enums import OptimizationCategory
from app.services.bundle import build_repositories
from app.services.notifications import BenchmarkNotifier
from app.services.optimization import OptimizationRecommendationService
from app.types import EventPublisher

logger = get_logger("app.workers.capacity_threshold_sweep")

_SOURCE_SERVICE = "performance-benchmark-framework"


class CapacityThresholdSweepWorker:
    """Notifies of newly-breached capacity forecasts, per capacity
    model."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher,
        notifier: BenchmarkNotifier,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._notifier = notifier
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every capacity model with a newly-breached
        forecast, returning how many were notified."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            optimization_service = OptimizationRecommendationService(
                repos.optimization_recommendations, publish=self._publish, notifier=self._notifier
            )

            for organization_id in await repos.capacity_forecasts.list_organization_ids():
                for capacity_model_id in await repos.capacity_forecasts.list_distinct_model_ids(
                    organization_id
                ):
                    latest = await repos.capacity_forecasts.list_latest_by_model(
                        organization_id, capacity_model_id=capacity_model_id, limit=1
                    )
                    if not latest:
                        continue
                    forecast = latest[0]
                    if forecast.created_at < lookback_cutoff:
                        continue
                    if not is_threshold_breached(
                        projected_value=forecast.projected_value,
                        threshold_value=forecast.threshold_value,
                    ):
                        continue

                    model = await repos.capacity_models.require_by_id(capacity_model_id)

                    await self._publish(
                        CapacityThresholdReachedEvent(
                            source_service=_SOURCE_SERVICE,
                            organization_id=organization_id,
                            payload={
                                "capacity_forecast_id": str(forecast.id),
                                "capacity_model_id": str(capacity_model_id),
                            },
                        )
                    )
                    await self._notifier.notify_capacity_warning(
                        resource_name=model.name,
                        projected_value=forecast.projected_value,
                        threshold_value=forecast.threshold_value,
                    )
                    await optimization_service.create(
                        organization_id,
                        category=OptimizationCategory.SCALING,
                        title=f"Scale {model.name} ahead of capacity threshold",
                        detail=(
                            f"{model.name} is forecast to reach {forecast.projected_value:.1f}, "
                            f"at or beyond its own threshold of {forecast.threshold_value:.1f}."
                        ),
                        magnitude_percent=(
                            (forecast.projected_value / forecast.threshold_value) * 100.0
                            if forecast.threshold_value
                            else 100.0
                        ),
                    )
                    notified += 1
            await session.commit()

        logger.info(
            "capacity threshold sweep completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["CapacityThresholdSweepWorker"]
