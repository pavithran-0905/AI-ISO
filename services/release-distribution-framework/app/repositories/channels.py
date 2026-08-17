"""Repository for release channel configurations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channels import ReleaseChannelConfig

MAX_PAGE_SIZE = 500


class ReleaseChannelConfigRepository(BaseRepository[ReleaseChannelConfig]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseChannelConfig, tenant_scope=tenant_scope)

    async def find_by_type(
        self, organization_id: UUID, *, channel_type: str
    ) -> ReleaseChannelConfig | None:
        stmt = self._base_select().where(
            ReleaseChannelConfig.organization_id == organization_id,
            ReleaseChannelConfig.channel_type == channel_type,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseChannelConfig]:
        stmt = (
            self._base_select()
            .where(ReleaseChannelConfig.organization_id == organization_id)
            .order_by(ReleaseChannelConfig.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleaseChannelConfigRepository"]
