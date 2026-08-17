"""Repositories for release packages and the artifacts within them."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.packages import ReleaseArtifact, ReleasePackage

MAX_PAGE_SIZE = 500


class ReleasePackageRepository(BaseRepository[ReleasePackage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleasePackage, tenant_scope=tenant_scope)

    async def list_for_version(self, release_version_id: UUID) -> Sequence[ReleasePackage]:
        stmt = self._base_select().where(ReleasePackage.release_version_id == release_version_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleasePackage]:
        stmt = (
            self._base_select()
            .where(ReleasePackage.organization_id == organization_id)
            .order_by(ReleasePackage.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ReleaseArtifactRepository(BaseRepository[ReleaseArtifact]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseArtifact, tenant_scope=tenant_scope)

    async def list_for_package(self, release_package_id: UUID) -> Sequence[ReleaseArtifact]:
        stmt = self._base_select().where(ReleaseArtifact.release_package_id == release_package_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseArtifact]:
        stmt = (
            self._base_select()
            .where(ReleaseArtifact.organization_id == organization_id)
            .order_by(ReleaseArtifact.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleaseArtifactRepository", "ReleasePackageRepository"]
