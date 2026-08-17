"""Repositories for capacity models and their forecasts."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capacity import CapacityForecast, CapacityModel

MAX_PAGE_SIZE = 500


class CapacityModelRepository(BaseRepository[CapacityModel]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CapacityModel, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[CapacityModel]:
        stmt = (
            self._base_select()
            .where(CapacityModel.organization_id == organization_id)
            .order_by(CapacityModel.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class CapacityForecastRepository(BaseRepository[CapacityForecast]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CapacityForecast, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[CapacityForecast]:
        stmt = (
            self._base_select()
            .where(CapacityForecast.organization_id == organization_id)
            .order_by(CapacityForecast.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_latest_by_model(
        self, organization_id: UUID, *, capacity_model_id: UUID, limit: int = 1
    ) -> Sequence[CapacityForecast]:
        stmt = (
            self._base_select()
            .where(
                CapacityForecast.organization_id == organization_id,
                CapacityForecast.capacity_model_id == capacity_model_id,
            )
            .order_by(CapacityForecast.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_distinct_model_ids(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[UUID]:
        stmt = (
            select(CapacityForecast.capacity_model_id)
            .where(CapacityForecast.organization_id == organization_id)
            .distinct()
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CapacityForecast.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CapacityForecastRepository", "CapacityModelRepository"]
