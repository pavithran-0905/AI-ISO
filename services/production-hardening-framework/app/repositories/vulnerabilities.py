"""Repository for vulnerability scan results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RemediationStatus
from app.models.vulnerabilities import VulnerabilityScan

MAX_PAGE_SIZE = 500

_OPEN_STATUSES = (RemediationStatus.OPEN, RemediationStatus.IN_PROGRESS)


class VulnerabilityScanRepository(BaseRepository[VulnerabilityScan]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, VulnerabilityScan, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[VulnerabilityScan]:
        stmt = (
            self._base_select()
            .where(VulnerabilityScan.organization_id == organization_id)
            .order_by(VulnerabilityScan.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_open(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[VulnerabilityScan]:
        stmt = (
            self._base_select()
            .where(
                VulnerabilityScan.organization_id == organization_id,
                VulnerabilityScan.status.in_(_OPEN_STATUSES),
            )
            .order_by(VulnerabilityScan.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(VulnerabilityScan.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "VulnerabilityScanRepository"]
