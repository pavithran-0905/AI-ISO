"""Repository for optimization recommendations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RecommendationStatus
from app.models.optimization import OptimizationRecommendation

MAX_PAGE_SIZE = 500


class OptimizationRecommendationRepository(BaseRepository[OptimizationRecommendation]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, OptimizationRecommendation, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[OptimizationRecommendation]:
        stmt = (
            self._base_select()
            .where(OptimizationRecommendation.organization_id == organization_id)
            .order_by(OptimizationRecommendation.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: RecommendationStatus, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[OptimizationRecommendation]:
        stmt = (
            self._base_select()
            .where(
                OptimizationRecommendation.organization_id == organization_id,
                OptimizationRecommendation.status == status,
            )
            .order_by(OptimizationRecommendation.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "OptimizationRecommendationRepository"]
