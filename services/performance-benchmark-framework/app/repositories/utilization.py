"""Repository for point-in-time resource utilization samples."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ResourceType
from app.models.utilization import ResourceUtilization

MAX_PAGE_SIZE = 500


class ResourceUtilizationRepository(BaseRepository[ResourceUtilization]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ResourceUtilization, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ResourceUtilization]:
        stmt = (
            self._base_select()
            .where(ResourceUtilization.organization_id == organization_id)
            .order_by(ResourceUtilization.recorded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent_by_type(
        self, organization_id: UUID, *, resource_type: ResourceType, limit: int = 100
    ) -> Sequence[ResourceUtilization]:
        stmt = (
            self._base_select()
            .where(
                ResourceUtilization.organization_id == organization_id,
                ResourceUtilization.resource_type == resource_type,
            )
            .order_by(ResourceUtilization.recorded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ResourceUtilizationRepository"]
