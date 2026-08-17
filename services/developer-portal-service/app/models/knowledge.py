"""Knowledge base articles and the portal's own search index."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ContentStatus, KnowledgeArticleCategory, SearchContentType


class KnowledgeArticle(BaseModel):
    """``knowledge_articles`` -- one published (or draft) knowledge base
    article."""

    __tablename__ = "knowledge_articles"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_knowledge_article_slug"),
        Index("ix_knowledge_article_category", "category"),
        Index("ix_knowledge_article_status", "status"),
    )

    slug: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[KnowledgeArticleCategory] = mapped_column(String(24), index=True)
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.DRAFT, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SearchIndexEntry(BaseModel):
    """``search_index`` -- one indexed piece of content, spanning every
    searchable content type this portal owns.

    Own, deliberately simple full-text index (title/summary/keywords),
    per docs/074's own "DO NOT IMPLEMENT: External Search Engines" --
    this is not a live Elasticsearch/OpenSearch integration.
    """

    __tablename__ = "search_index"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "content_type", "content_id", name="uq_search_index_entry"
        ),
        Index("ix_search_index_content_type", "content_type"),
    )

    content_type: Mapped[SearchContentType] = mapped_column(String(16), index=True)
    content_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["KnowledgeArticle", "SearchIndexEntry"]
