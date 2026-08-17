"""Repositories for documentation pages, their version history, and
reader feedback."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documentation import DocumentationFeedback, DocumentationPage, DocumentationVersion
from app.models.enums import ContentStatus

MAX_PAGE_SIZE = 500


class DocumentationPageRepository(BaseRepository[DocumentationPage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentationPage, tenant_scope=tenant_scope)

    async def find_by_slug(self, organization_id: UUID, *, slug: str) -> DocumentationPage | None:
        stmt = self._base_select().where(
            DocumentationPage.organization_id == organization_id, DocumentationPage.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_published(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[DocumentationPage]:
        stmt = (
            self._base_select()
            .where(
                DocumentationPage.organization_id == organization_id,
                DocumentationPage.status == ContentStatus.PUBLISHED,
            )
            .order_by(DocumentationPage.published_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 500
    ) -> Sequence[DocumentationPage]:
        stmt = (
            self._base_select()
            .where(DocumentationPage.organization_id == organization_id)
            .order_by(DocumentationPage.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DocumentationPage.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DocumentationVersionRepository(BaseRepository[DocumentationVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentationVersion, tenant_scope=tenant_scope)

    async def list_for_page(self, documentation_page_id: UUID) -> Sequence[DocumentationVersion]:
        stmt = (
            self._base_select()
            .where(DocumentationVersion.documentation_page_id == documentation_page_id)
            .order_by(DocumentationVersion.published_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


class DocumentationFeedbackRepository(BaseRepository[DocumentationFeedback]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentationFeedback, tenant_scope=tenant_scope)

    async def list_for_page(self, documentation_page_id: UUID) -> Sequence[DocumentationFeedback]:
        stmt = self._base_select().where(
            DocumentationFeedback.documentation_page_id == documentation_page_id
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "DocumentationFeedbackRepository",
    "DocumentationPageRepository",
    "DocumentationVersionRepository",
]
