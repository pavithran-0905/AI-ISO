"""Repositories for community posts and comments."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import CommunityComment, CommunityPost
from app.models.enums import CommunityPostType, ModerationStatus

MAX_PAGE_SIZE = 500


class CommunityPostRepository(BaseRepository[CommunityPost]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CommunityPost, tenant_scope=tenant_scope)

    async def list_visible(
        self,
        organization_id: UUID,
        *,
        post_type: CommunityPostType | None = None,
        limit: int = 100,
    ) -> Sequence[CommunityPost]:
        stmt = self._base_select().where(
            CommunityPost.organization_id == organization_id,
            CommunityPost.moderation_status == ModerationStatus.VISIBLE,
        )
        if post_type is not None:
            stmt = stmt.where(CommunityPost.post_type == post_type)
        stmt = stmt.order_by(CommunityPost.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CommunityPost.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CommunityCommentRepository(BaseRepository[CommunityComment]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CommunityComment, tenant_scope=tenant_scope)

    async def list_for_post(self, community_post_id: UUID) -> Sequence[CommunityComment]:
        stmt = (
            self._base_select()
            .where(
                CommunityComment.community_post_id == community_post_id,
                CommunityComment.moderation_status == ModerationStatus.VISIBLE,
            )
            .order_by(CommunityComment.created_at.asc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CommunityCommentRepository", "CommunityPostRepository"]
