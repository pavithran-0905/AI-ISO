"""AI documentation assistant.

Publishes ``AIAssistantUsed`` on every question asked, and notifies AI
Recommendation directly when the assistant answers confidently.
"""

from __future__ import annotations

from uuid import UUID

from app.assistant.engine import AssistantAnswer, answer_question
from app.events.domain_events import AIAssistantUsedEvent
from app.repositories.knowledge import SearchIndexEntryRepository
from app.search.engine import SearchCandidate
from app.services.notifications import PortalNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class AssistantService:
    def __init__(
        self,
        repo: SearchIndexEntryRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: PortalNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def ask(
        self,
        organization_id: UUID,
        *,
        question: str,
        user_id: str,
        confidence_threshold: float = 0.5,
    ) -> AssistantAnswer:
        entries = await self._repo.list_all(organization_id)
        candidates = [
            (
                str(entry.content_id),
                SearchCandidate(title=entry.title, summary=entry.summary, keywords=entry.keywords),
            )
            for entry in entries
        ]
        answer = answer_question(question, candidates, confidence_threshold=confidence_threshold)

        await self._publish(
            AIAssistantUsedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"user_id": user_id, "confidence": answer.confidence},
            )
        )
        if (
            answer.content_id is not None
            and answer.title is not None
            and self._notifier is not None
        ):
            await self._notifier.notify_ai_recommendation(title=answer.title)
        return answer


__all__ = ["AssistantService"]
