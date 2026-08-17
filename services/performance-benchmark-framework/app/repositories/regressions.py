"""Repository for detected performance regressions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regressions import PerformanceRegression

MAX_PAGE_SIZE = 500


class PerformanceRegressionRepository(BaseRepository[PerformanceRegression]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PerformanceRegression, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[PerformanceRegression]:
        stmt = (
            self._base_select()
            .where(PerformanceRegression.organization_id == organization_id)
            .order_by(PerformanceRegression.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_since(self, organization_id: UUID, *, since: datetime, until: datetime) -> int:
        """Count regressions created within ``[since, until)``, used by
        the statistics rollup worker's own windowed count."""
        stmt = select(func.count()).where(
            PerformanceRegression.organization_id == organization_id,
            PerformanceRegression.created_at >= since,
            PerformanceRegression.created_at < until,
        )
        return int((await self._session.execute(stmt)).scalar_one())


__all__ = ["MAX_PAGE_SIZE", "PerformanceRegressionRepository"]
