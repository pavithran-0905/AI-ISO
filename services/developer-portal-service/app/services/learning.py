"""Tutorials and learning paths.

Notifies Tutorial Available directly on a tutorial's own
``-> PUBLISHED`` transition (there is no dedicated publish event for
tutorials, unlike documentation pages), and publishes
``TutorialCompleted`` on a caller's own report that a tutorial was
completed -- see ``app.tutorials.engine`` for why completion itself is
never persisted.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.documentation.engine import TransitionResult, validate_transition
from app.events.domain_events import TutorialCompletedEvent
from app.models.enums import ContentStatus, TutorialDifficulty
from app.models.learning import LearningPath, Tutorial
from app.repositories.learning import LearningPathRepository, TutorialRepository
from app.services.notifications import PortalNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class TutorialService:
    def __init__(
        self,
        repo: TutorialRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: PortalNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def create(
        self,
        organization_id: UUID,
        *,
        slug: str,
        title: str,
        description: str = "",
        difficulty: TutorialDifficulty = TutorialDifficulty.BEGINNER,
        estimated_minutes: int = 15,
    ) -> Tutorial:
        return await self._repo.create(
            Tutorial(
                organization_id=organization_id,
                slug=slug,
                title=title,
                description=description,
                difficulty=difficulty,
                estimated_minutes=estimated_minutes,
            )
        )

    async def transition(
        self, tutorial: Tutorial, *, target: ContentStatus, now: datetime
    ) -> Tutorial:
        result = validate_transition(tutorial.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        tutorial.status = target
        if target == ContentStatus.PUBLISHED:
            tutorial.published_at = now
        await self._repo.update(tutorial)

        if target == ContentStatus.PUBLISHED and self._notifier is not None:
            await self._notifier.notify_tutorial_available(title=tutorial.title)
        return tutorial

    async def complete(self, tutorial: Tutorial, *, user_id: str) -> None:
        """Record a caller-reported tutorial completion. Publishes
        ``TutorialCompleted`` without writing any new row -- there is
        nowhere in this service's own schema for per-user completion
        state to live."""
        await self._publish(
            TutorialCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=tutorial.organization_id,
                payload={"tutorial_id": str(tutorial.id), "user_id": user_id},
            )
        )


class LearningPathService:
    def __init__(self, repo: LearningPathRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        slug: str,
        title: str,
        description: str = "",
        tutorial_ids: list[str] | None = None,
    ) -> LearningPath:
        return await self._repo.create(
            LearningPath(
                organization_id=organization_id,
                slug=slug,
                title=title,
                description=description,
                tutorial_ids=tutorial_ids or [],
            )
        )


__all__ = ["LearningPathService", "TransitionRefusedError", "TutorialService"]
