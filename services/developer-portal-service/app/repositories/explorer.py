"""Repositories for playground sessions, saved GraphQL queries, and
webhook tests."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlaygroundSessionStatus
from app.models.explorer import GraphQlQuery, PlaygroundSession, WebhookTest

MAX_PAGE_SIZE = 500


class PlaygroundSessionRepository(BaseRepository[PlaygroundSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PlaygroundSession, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[PlaygroundSession]:
        stmt = (
            self._base_select()
            .where(
                PlaygroundSession.organization_id == organization_id,
                PlaygroundSession.status == PlaygroundSessionStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[PlaygroundSession]:
        stmt = (
            self._base_select()
            .where(
                PlaygroundSession.organization_id == organization_id,
                PlaygroundSession.user_id == user_id,
            )
            .order_by(PlaygroundSession.last_active_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(PlaygroundSession.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class GraphQlQueryRepository(BaseRepository[GraphQlQuery]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, GraphQlQuery, tenant_scope=tenant_scope)

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[GraphQlQuery]:
        stmt = (
            self._base_select()
            .where(GraphQlQuery.organization_id == organization_id, GraphQlQuery.user_id == user_id)
            .order_by(GraphQlQuery.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class WebhookTestRepository(BaseRepository[WebhookTest]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, WebhookTest, tenant_scope=tenant_scope)

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[WebhookTest]:
        stmt = (
            self._base_select()
            .where(WebhookTest.organization_id == organization_id, WebhookTest.user_id == user_id)
            .order_by(WebhookTest.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "GraphQlQueryRepository",
    "PlaygroundSessionRepository",
    "WebhookTestRepository",
]
