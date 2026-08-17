"""Repository for the certificate inventory."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificates import CertificateInventoryEntry

MAX_PAGE_SIZE = 500


class CertificateInventoryRepository(BaseRepository[CertificateInventoryEntry]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CertificateInventoryEntry, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[CertificateInventoryEntry]:
        stmt = (
            self._base_select()
            .where(CertificateInventoryEntry.organization_id == organization_id)
            .order_by(CertificateInventoryEntry.expires_at.asc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_valid(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[CertificateInventoryEntry]:
        stmt = (
            self._base_select()
            .where(
                CertificateInventoryEntry.organization_id == organization_id,
                CertificateInventoryEntry.is_valid.is_(True),
            )
            .order_by(CertificateInventoryEntry.expires_at.asc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CertificateInventoryEntry.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CertificateInventoryRepository"]
