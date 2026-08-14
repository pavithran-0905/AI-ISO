"""Repositories for the fleet tables: clusters, gateways, devices, and
inventory."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.devices import EdgeCluster, EdgeDevice, EdgeGateway, EdgeInventory
from app.models.enums import DeviceLifecycleState, EdgeDeviceType

MAX_PAGE_SIZE = 500


class EdgeClusterRepository(BaseRepository[EdgeCluster]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeCluster, tenant_scope=tenant_scope)

    async def list_for_site(self, site_id: UUID) -> Sequence[EdgeCluster]:
        stmt = self._base_select().where(EdgeCluster.site_id == site_id)
        return (await self._session.execute(stmt)).scalars().all()


class EdgeGatewayRepository(BaseRepository[EdgeGateway]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeGateway, tenant_scope=tenant_scope)

    async def list_for_site(self, site_id: UUID) -> Sequence[EdgeGateway]:
        stmt = self._base_select().where(EdgeGateway.site_id == site_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeGateway.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeDeviceRepository(BaseRepository[EdgeDevice]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeDevice, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, name: str) -> EdgeDevice | None:
        stmt = self._base_select().where(
            EdgeDevice.organization_id == organization_id, EdgeDevice.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(self, organization_id: UUID, device_id: UUID) -> EdgeDevice:
        stmt = self._base_select().where(
            EdgeDevice.id == device_id, EdgeDevice.organization_id == organization_id
        )
        found: EdgeDevice | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Edge device {device_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        site_id: UUID | None = None,
        lifecycle_state: DeviceLifecycleState | None = None,
        device_type: EdgeDeviceType | None = None,
        limit: int = 100,
    ) -> Sequence[EdgeDevice]:
        stmt = self._base_select().where(EdgeDevice.organization_id == organization_id)
        if site_id is not None:
            stmt = stmt.where(EdgeDevice.site_id == site_id)
        if lifecycle_state is not None:
            stmt = stmt.where(EdgeDevice.lifecycle_state == lifecycle_state)
        if device_type is not None:
            stmt = stmt.where(EdgeDevice.device_type == device_type)
        stmt = stmt.order_by(EdgeDevice.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeDevice.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeInventoryRepository(BaseRepository[EdgeInventory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeInventory, tenant_scope=tenant_scope)

    async def latest_for_device(
        self, device_id: UUID, *, resource_kind: str
    ) -> EdgeInventory | None:
        stmt = (
            self._base_select()
            .where(
                EdgeInventory.device_id == device_id, EdgeInventory.resource_kind == resource_kind
            )
            .order_by(EdgeInventory.collected_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeInventory]:
        stmt = self._base_select().where(EdgeInventory.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "EdgeClusterRepository",
    "EdgeDeviceRepository",
    "EdgeGatewayRepository",
    "EdgeInventoryRepository",
]
