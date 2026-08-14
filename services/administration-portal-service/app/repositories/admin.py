"""Repositories for administrator sessions and administrative actions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminAction, AdminSession

MAX_PAGE_SIZE = 500


class AdminSessionRepository(BaseRepository[AdminSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, AdminSession, tenant_scope=tenant_scope)

    async def list_for_admin_user(self, admin_user_id: str) -> Sequence[AdminSession]:
        stmt = self._base_select().where(AdminSession.admin_user_id == admin_user_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_enabled(self, organization_id: UUID) -> Sequence[AdminSession]:
        stmt = self._base_select().where(
            AdminSession.organization_id == organization_id, AdminSession.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()


class AdminActionRepository(BaseRepository[AdminAction]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, AdminAction, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[AdminAction]:
        stmt = self._base_select().where(AdminAction.organization_id == organization_id)
        if since is not None:
            stmt = stmt.where(AdminAction.performed_at >= since)
        stmt = stmt.order_by(AdminAction.performed_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "AdminActionRepository", "AdminSessionRepository"]
