"""Repository for hardening profiles."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hardening_definitions import HardeningProfile

MAX_PAGE_SIZE = 500


class HardeningProfileRepository(BaseRepository[HardeningProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HardeningProfile, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[HardeningProfile]:
        stmt = (
            self._base_select()
            .where(HardeningProfile.organization_id == organization_id)
            .order_by(HardeningProfile.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "HardeningProfileRepository"]
