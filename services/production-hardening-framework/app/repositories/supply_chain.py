"""Repositories for the SBOM catalog and signed release artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supply_chain import SbomCatalog, SignedArtifact

MAX_PAGE_SIZE = 500


class SbomCatalogRepository(BaseRepository[SbomCatalog]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SbomCatalog, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SbomCatalog]:
        stmt = (
            self._base_select()
            .where(SbomCatalog.organization_id == organization_id)
            .order_by(SbomCatalog.generated_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class SignedArtifactRepository(BaseRepository[SignedArtifact]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SignedArtifact, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SignedArtifact]:
        stmt = (
            self._base_select()
            .where(SignedArtifact.organization_id == organization_id)
            .order_by(SignedArtifact.signed_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "SbomCatalogRepository", "SignedArtifactRepository"]
