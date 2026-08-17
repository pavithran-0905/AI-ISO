"""Repositories for knowledge base articles and the search index."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ContentStatus, KnowledgeArticleCategory, SearchContentType
from app.models.knowledge import KnowledgeArticle, SearchIndexEntry

MAX_PAGE_SIZE = 500


class KnowledgeArticleRepository(BaseRepository[KnowledgeArticle]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, KnowledgeArticle, tenant_scope=tenant_scope)

    async def find_by_slug(self, organization_id: UUID, *, slug: str) -> KnowledgeArticle | None:
        stmt = self._base_select().where(
            KnowledgeArticle.organization_id == organization_id, KnowledgeArticle.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_published(
        self,
        organization_id: UUID,
        *,
        category: KnowledgeArticleCategory | None = None,
        limit: int = 100,
    ) -> Sequence[KnowledgeArticle]:
        stmt = self._base_select().where(
            KnowledgeArticle.organization_id == organization_id,
            KnowledgeArticle.status == ContentStatus.PUBLISHED,
        )
        if category is not None:
            stmt = stmt.where(KnowledgeArticle.category == category)
        stmt = stmt.order_by(KnowledgeArticle.published_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(KnowledgeArticle.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class SearchIndexEntryRepository(BaseRepository[SearchIndexEntry]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SearchIndexEntry, tenant_scope=tenant_scope)

    async def find(
        self, organization_id: UUID, *, content_type: SearchContentType, content_id: UUID
    ) -> SearchIndexEntry | None:
        stmt = self._base_select().where(
            SearchIndexEntry.organization_id == organization_id,
            SearchIndexEntry.content_type == content_type,
            SearchIndexEntry.content_id == content_id,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self,
        organization_id: UUID,
        *,
        content_type: SearchContentType | None = None,
        limit: int = MAX_PAGE_SIZE,
    ) -> Sequence[SearchIndexEntry]:
        stmt = self._base_select().where(SearchIndexEntry.organization_id == organization_id)
        if content_type is not None:
            stmt = stmt.where(SearchIndexEntry.content_type == content_type)
        stmt = stmt.limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SearchIndexEntry.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "KnowledgeArticleRepository", "SearchIndexEntryRepository"]
