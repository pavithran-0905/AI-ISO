"""Repositories for tutorials and learning paths."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ContentStatus
from app.models.learning import LearningPath, Tutorial

MAX_PAGE_SIZE = 500


class TutorialRepository(BaseRepository[Tutorial]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Tutorial, tenant_scope=tenant_scope)

    async def find_by_slug(self, organization_id: UUID, *, slug: str) -> Tutorial | None:
        stmt = self._base_select().where(
            Tutorial.organization_id == organization_id, Tutorial.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_published(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[Tutorial]:
        stmt = (
            self._base_select()
            .where(
                Tutorial.organization_id == organization_id,
                Tutorial.status == ContentStatus.PUBLISHED,
            )
            .order_by(Tutorial.published_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Tutorial.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class LearningPathRepository(BaseRepository[LearningPath]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LearningPath, tenant_scope=tenant_scope)

    async def find_by_slug(self, organization_id: UUID, *, slug: str) -> LearningPath | None:
        stmt = self._base_select().where(
            LearningPath.organization_id == organization_id, LearningPath.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_published(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[LearningPath]:
        stmt = (
            self._base_select()
            .where(
                LearningPath.organization_id == organization_id,
                LearningPath.status == ContentStatus.PUBLISHED,
            )
            .order_by(LearningPath.published_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "LearningPathRepository", "TutorialRepository"]
