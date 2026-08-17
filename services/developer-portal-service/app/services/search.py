"""Full-text/keyword search across every indexed content type.

Publishes ``SearchPerformed`` on every search.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import SearchPerformedEvent
from app.models.enums import SearchContentType
from app.repositories.knowledge import SearchIndexEntryRepository
from app.search.engine import SearchCandidate, rank_candidates
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SearchService:
    def __init__(
        self, repo: SearchIndexEntryRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def search(
        self,
        organization_id: UUID,
        *,
        query: str,
        user_id: str,
        content_type: SearchContentType | None = None,
        limit: int = 20,
    ) -> list[tuple[UUID, float]]:
        entries = await self._repo.list_all(organization_id, content_type=content_type)
        candidates = [
            (
                str(entry.content_id),
                SearchCandidate(title=entry.title, summary=entry.summary, keywords=entry.keywords),
            )
            for entry in entries
        ]
        ranked = rank_candidates(query, candidates)[:limit]
        results = [(UUID(identifier), score) for identifier, score in ranked]

        await self._publish(
            SearchPerformedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"user_id": user_id, "query": query, "result_count": len(results)},
            )
        )
        return results


__all__ = ["SearchService"]
