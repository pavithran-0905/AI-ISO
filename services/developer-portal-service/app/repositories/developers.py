"""Repositories for developer profiles, portal sessions, bookmarks, and
favorites."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.developers import (
    DeveloperBookmark,
    DeveloperFavorite,
    DeveloperProfile,
    DeveloperSession,
)
from app.models.enums import DeveloperSessionStatus, SearchContentType

MAX_PAGE_SIZE = 500


class DeveloperProfileRepository(BaseRepository[DeveloperProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperProfile, tenant_scope=tenant_scope)

    async def find_by_user(self, organization_id: UUID, *, user_id: str) -> DeveloperProfile | None:
        stmt = self._base_select().where(
            DeveloperProfile.organization_id == organization_id, DeveloperProfile.user_id == user_id
        )
        return (await self._session.execute(stmt)).scalars().first()


class DeveloperSessionRepository(BaseRepository[DeveloperSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperSession, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DeveloperSession]:
        stmt = (
            self._base_select()
            .where(
                DeveloperSession.organization_id == organization_id,
                DeveloperSession.status == DeveloperSessionStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DeveloperSession.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DeveloperBookmarkRepository(BaseRepository[DeveloperBookmark]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperBookmark, tenant_scope=tenant_scope)

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[DeveloperBookmark]:
        stmt = (
            self._base_select()
            .where(
                DeveloperBookmark.organization_id == organization_id,
                DeveloperBookmark.user_id == user_id,
            )
            .order_by(DeveloperBookmark.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        content_type: SearchContentType,
        content_id: UUID,
    ) -> DeveloperBookmark | None:
        stmt = self._base_select().where(
            DeveloperBookmark.organization_id == organization_id,
            DeveloperBookmark.user_id == user_id,
            DeveloperBookmark.content_type == content_type,
            DeveloperBookmark.content_id == content_id,
        )
        return (await self._session.execute(stmt)).scalars().first()


class DeveloperFavoriteRepository(BaseRepository[DeveloperFavorite]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperFavorite, tenant_scope=tenant_scope)

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[DeveloperFavorite]:
        stmt = (
            self._base_select()
            .where(
                DeveloperFavorite.organization_id == organization_id,
                DeveloperFavorite.user_id == user_id,
            )
            .order_by(DeveloperFavorite.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        content_type: SearchContentType,
        content_id: UUID,
    ) -> DeveloperFavorite | None:
        stmt = self._base_select().where(
            DeveloperFavorite.organization_id == organization_id,
            DeveloperFavorite.user_id == user_id,
            DeveloperFavorite.content_type == content_type,
            DeveloperFavorite.content_id == content_id,
        )
        return (await self._session.execute(stmt)).scalars().first()


__all__ = [
    "MAX_PAGE_SIZE",
    "DeveloperBookmarkRepository",
    "DeveloperFavoriteRepository",
    "DeveloperProfileRepository",
    "DeveloperSessionRepository",
]
