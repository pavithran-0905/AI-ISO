"""Repository for production certifications."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certification import ProductionCertification
from app.models.enums import CertificationStatus

MAX_PAGE_SIZE = 500


class ProductionCertificationRepository(BaseRepository[ProductionCertification]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ProductionCertification, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ProductionCertification]:
        stmt = (
            self._base_select()
            .where(ProductionCertification.organization_id == organization_id)
            .order_by(ProductionCertification.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: CertificationStatus, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ProductionCertification]:
        stmt = (
            self._base_select()
            .where(
                ProductionCertification.organization_id == organization_id,
                ProductionCertification.status == status,
            )
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ProductionCertification.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ProductionCertificationRepository"]
