"""Repositories for the site hierarchy tables: sites and locations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sites import EdgeLocation, EdgeSite

MAX_PAGE_SIZE = 500


class EdgeSiteRepository(BaseRepository[EdgeSite]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeSite, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, name: str) -> EdgeSite | None:
        stmt = self._base_select().where(
            EdgeSite.organization_id == organization_id, EdgeSite.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(self, organization_id: UUID, site_id: UUID) -> EdgeSite:
        stmt = self._base_select().where(
            EdgeSite.id == site_id, EdgeSite.organization_id == organization_id
        )
        found: EdgeSite | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Edge site {site_id!s} was not found in this organization.")
        return found

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[EdgeSite]:
        stmt = (
            self._base_select()
            .where(EdgeSite.organization_id == organization_id)
            .order_by(EdgeSite.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeSite.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeLocationRepository(BaseRepository[EdgeLocation]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeLocation, tenant_scope=tenant_scope)

    async def list_for_site(self, site_id: UUID) -> Sequence[EdgeLocation]:
        stmt = self._base_select().where(EdgeLocation.site_id == site_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_children(self, parent_location_id: UUID) -> Sequence[EdgeLocation]:
        stmt = self._base_select().where(EdgeLocation.parent_location_id == parent_location_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "EdgeLocationRepository", "EdgeSiteRepository"]
