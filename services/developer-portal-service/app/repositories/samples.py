"""Repositories for sample projects and their code snippets."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ContentStatus, SampleProjectCategory
from app.models.samples import CodeSnippet, SampleProject

MAX_PAGE_SIZE = 500


class SampleProjectRepository(BaseRepository[SampleProject]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SampleProject, tenant_scope=tenant_scope)

    async def find_by_slug(self, organization_id: UUID, *, slug: str) -> SampleProject | None:
        stmt = self._base_select().where(
            SampleProject.organization_id == organization_id, SampleProject.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_published(
        self,
        organization_id: UUID,
        *,
        category: SampleProjectCategory | None = None,
        limit: int = 100,
    ) -> Sequence[SampleProject]:
        stmt = self._base_select().where(
            SampleProject.organization_id == organization_id,
            SampleProject.status == ContentStatus.PUBLISHED,
        )
        if category is not None:
            stmt = stmt.where(SampleProject.category == category)
        stmt = stmt.order_by(SampleProject.published_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SampleProject.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CodeSnippetRepository(BaseRepository[CodeSnippet]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CodeSnippet, tenant_scope=tenant_scope)

    async def list_for_sample(self, sample_project_id: UUID) -> Sequence[CodeSnippet]:
        stmt = self._base_select().where(CodeSnippet.sample_project_id == sample_project_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CodeSnippetRepository", "SampleProjectRepository"]
