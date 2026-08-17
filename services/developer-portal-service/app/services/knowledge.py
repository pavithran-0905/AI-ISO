"""Knowledge base articles and search index maintenance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.documentation.engine import TransitionResult, validate_transition
from app.models.enums import ContentStatus, KnowledgeArticleCategory, SearchContentType
from app.models.knowledge import KnowledgeArticle, SearchIndexEntry
from app.repositories.knowledge import KnowledgeArticleRepository, SearchIndexEntryRepository


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class KnowledgeArticleService:
    def __init__(self, repo: KnowledgeArticleRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        slug: str,
        title: str,
        content: str,
        category: KnowledgeArticleCategory,
    ) -> KnowledgeArticle:
        return await self._repo.create(
            KnowledgeArticle(
                organization_id=organization_id,
                slug=slug,
                title=title,
                content=content,
                category=category,
            )
        )

    async def transition(
        self, article: KnowledgeArticle, *, target: ContentStatus, now: datetime
    ) -> KnowledgeArticle:
        result = validate_transition(article.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        article.status = target
        if target == ContentStatus.PUBLISHED:
            article.published_at = now
        return await self._repo.update(article)


class SearchIndexService:
    def __init__(self, repo: SearchIndexEntryRepository) -> None:
        self._repo = repo

    async def index(
        self,
        organization_id: UUID,
        *,
        content_type: SearchContentType,
        content_id: UUID,
        title: str,
        summary: str,
        keywords: list[str],
        now: datetime,
    ) -> SearchIndexEntry:
        """Index (or re-index) one piece of content, upserting by its
        own ``(content_type, content_id)`` identity."""
        existing = await self._repo.find(
            organization_id, content_type=content_type, content_id=content_id
        )
        if existing is not None:
            existing.title = title
            existing.summary = summary
            existing.keywords = keywords
            existing.indexed_at = now
            return await self._repo.update(existing)
        return await self._repo.create(
            SearchIndexEntry(
                organization_id=organization_id,
                content_type=content_type,
                content_id=content_id,
                title=title,
                summary=summary,
                keywords=keywords,
                indexed_at=now,
            )
        )


__all__ = ["KnowledgeArticleService", "SearchIndexService", "TransitionRefusedError"]
