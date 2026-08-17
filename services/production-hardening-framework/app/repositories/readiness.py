"""Repositories for operational readiness and disaster recovery checks."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.readiness import DisasterRecoveryCheck, OperationalReadiness

MAX_PAGE_SIZE = 500


class OperationalReadinessRepository(BaseRepository[OperationalReadiness]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, OperationalReadiness, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[OperationalReadiness]:
        stmt = (
            self._base_select()
            .where(OperationalReadiness.organization_id == organization_id)
            .order_by(OperationalReadiness.checked_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DisasterRecoveryCheckRepository(BaseRepository[DisasterRecoveryCheck]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DisasterRecoveryCheck, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DisasterRecoveryCheck]:
        stmt = (
            self._base_select()
            .where(DisasterRecoveryCheck.organization_id == organization_id)
            .order_by(DisasterRecoveryCheck.checked_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "DisasterRecoveryCheckRepository", "OperationalReadinessRepository"]
