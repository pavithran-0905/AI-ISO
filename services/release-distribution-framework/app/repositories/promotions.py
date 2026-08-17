"""Repository for release promotions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PromotionStatus
from app.models.promotions import ReleasePromotion

MAX_PAGE_SIZE = 500


class ReleasePromotionRepository(BaseRepository[ReleasePromotion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleasePromotion, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleasePromotion]:
        stmt = (
            self._base_select()
            .where(ReleasePromotion.organization_id == organization_id)
            .order_by(ReleasePromotion.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: PromotionStatus, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleasePromotion]:
        stmt = (
            self._base_select()
            .where(
                ReleasePromotion.organization_id == organization_id,
                ReleasePromotion.status == status,
            )
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ReleasePromotion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleasePromotionRepository"]
