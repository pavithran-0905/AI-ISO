"""Repositories for artifact checksums, signatures, and SBOM
publications."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supply_chain import ArtifactChecksum, ArtifactSignature, SbomPublication

MAX_PAGE_SIZE = 500


class ArtifactChecksumRepository(BaseRepository[ArtifactChecksum]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ArtifactChecksum, tenant_scope=tenant_scope)

    async def list_for_artifact(self, release_artifact_id: UUID) -> Sequence[ArtifactChecksum]:
        stmt = self._base_select().where(
            ArtifactChecksum.release_artifact_id == release_artifact_id
        )
        return (await self._session.execute(stmt)).scalars().all()


class ArtifactSignatureRepository(BaseRepository[ArtifactSignature]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ArtifactSignature, tenant_scope=tenant_scope)

    async def list_for_artifact(self, release_artifact_id: UUID) -> Sequence[ArtifactSignature]:
        stmt = self._base_select().where(
            ArtifactSignature.release_artifact_id == release_artifact_id
        )
        return (await self._session.execute(stmt)).scalars().all()


class SbomPublicationRepository(BaseRepository[SbomPublication]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SbomPublication, tenant_scope=tenant_scope)

    async def list_for_version(self, release_version_id: UUID) -> Sequence[SbomPublication]:
        stmt = self._base_select().where(SbomPublication.release_version_id == release_version_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SbomPublication]:
        stmt = (
            self._base_select()
            .where(SbomPublication.organization_id == organization_id)
            .order_by(SbomPublication.published_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["ArtifactChecksumRepository", "ArtifactSignatureRepository", "SbomPublicationRepository"]
