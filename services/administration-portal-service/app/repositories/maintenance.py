"""Repositories for maintenance windows and platform announcements."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceStatus
from app.models.maintenance import MaintenanceWindow, PlatformAnnouncement

MAX_PAGE_SIZE = 500


class MaintenanceWindowRepository(BaseRepository[MaintenanceWindow]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MaintenanceWindow, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, window_id: UUID) -> MaintenanceWindow:
        stmt = self._base_select().where(
            MaintenanceWindow.id == window_id, MaintenanceWindow.organization_id == organization_id
        )
        found: MaintenanceWindow | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Maintenance window {window_id!s} was not found in this organization."
            )
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: MaintenanceStatus | None = None, limit: int = 100
    ) -> Sequence[MaintenanceWindow]:
        stmt = self._base_select().where(MaintenanceWindow.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(MaintenanceWindow.status == status)
        stmt = stmt.order_by(MaintenanceWindow.starts_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: MaintenanceStatus
    ) -> Sequence[MaintenanceWindow]:
        stmt = self._base_select().where(
            MaintenanceWindow.organization_id == organization_id, MaintenanceWindow.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MaintenanceWindow.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class PlatformAnnouncementRepository(BaseRepository[PlatformAnnouncement]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PlatformAnnouncement, tenant_scope=tenant_scope)

    async def list_enabled(self, organization_id: UUID) -> Sequence[PlatformAnnouncement]:
        stmt = self._base_select().where(
            PlatformAnnouncement.organization_id == organization_id,
            PlatformAnnouncement.is_enabled.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "MaintenanceWindowRepository", "PlatformAnnouncementRepository"]
