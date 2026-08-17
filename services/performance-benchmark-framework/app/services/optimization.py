"""AI-assisted optimization recommendations (docs/078 "AI OPTIMIZATION",
integrating Prompt 060).

Generated automatically by the workers that detect the underlying fact
a recommendation would address -- the regression sweep worker for
query/workflow/API/infrastructure recommendations, the capacity
threshold sweep worker for scaling recommendations -- rather than
requiring a separate manual trigger, since this service has no
dedicated ``POST /optimization`` route.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import OptimizationGeneratedEvent
from app.models.enums import OptimizationCategory
from app.models.optimization import OptimizationRecommendation
from app.optimization.engine import compute_impact_score
from app.repositories.optimization import OptimizationRecommendationRepository
from app.services.notifications import BenchmarkNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "performance-benchmark-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class OptimizationRecommendationService:
    def __init__(
        self,
        repo: OptimizationRecommendationRepository,
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
        category: OptimizationCategory,
        title: str,
        detail: str,
        magnitude_percent: float,
        category_weight: float = 1.0,
    ) -> OptimizationRecommendation:
        impact_score = compute_impact_score(
            magnitude_percent=magnitude_percent, category_weight=category_weight
        )
        recommendation = await self._repo.create(
            OptimizationRecommendation(
                organization_id=organization_id,
                category=category,
                title=title,
                detail=detail,
                impact_score=impact_score,
            )
        )
        await self._publish(
            OptimizationGeneratedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "optimization_recommendation_id": str(recommendation.id),
                    "category": str(category),
                },
            )
        )
        if self._notifier is not None:
            if category == OptimizationCategory.SCALING:
                await self._notifier.notify_scaling_recommendation(
                    title=title, impact_score=impact_score
                )
            else:
                await self._notifier.notify_optimization_available(
                    title=title, impact_score=impact_score
                )
        return recommendation


__all__ = ["OptimizationRecommendationService"]
