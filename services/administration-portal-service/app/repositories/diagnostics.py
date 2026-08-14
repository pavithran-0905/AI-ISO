"""Repositories for diagnostic runs and component health checks."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnostics import Diagnostic, HealthCheck
from app.models.enums import DiagnosticCategory

MAX_PAGE_SIZE = 500


class DiagnosticRepository(BaseRepository[Diagnostic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Diagnostic, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, category: DiagnosticCategory | None = None, limit: int = 100
    ) -> Sequence[Diagnostic]:
        stmt = self._base_select().where(Diagnostic.organization_id == organization_id)
        if category is not None:
            stmt = stmt.where(Diagnostic.category == category)
        stmt = stmt.order_by(Diagnostic.ran_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class HealthCheckRepository(BaseRepository[HealthCheck]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, HealthCheck, tenant_scope=tenant_scope)

    async def find_by_component(
        self, organization_id: UUID, *, component: str
    ) -> HealthCheck | None:
        stmt = self._base_select().where(
            HealthCheck.organization_id == organization_id, HealthCheck.component == component
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(self, organization_id: UUID) -> Sequence[HealthCheck]:
        stmt = self._base_select().where(HealthCheck.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(HealthCheck.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "DiagnosticRepository", "HealthCheckRepository"]
