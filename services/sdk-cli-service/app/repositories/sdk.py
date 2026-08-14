"""Repositories for SDK languages, versions, packages, downloads, and
releases."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReleaseStatus, SdkLanguage
from app.models.sdk import SdkDownload, SdkLanguageCatalog, SdkPackage, SdkRelease, SdkVersion

MAX_PAGE_SIZE = 500


class SdkVersionRepository(BaseRepository[SdkVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkVersion, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, version_id: UUID) -> SdkVersion:
        stmt = self._base_select().where(
            SdkVersion.id == version_id, SdkVersion.organization_id == organization_id
        )
        found: SdkVersion | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"SDK version {version_id!s} was not found in this organization.")
        return found

    async def list_for_language(
        self, organization_id: UUID, *, language: SdkLanguage
    ) -> Sequence[SdkVersion]:
        stmt = self._base_select().where(
            SdkVersion.organization_id == organization_id, SdkVersion.language == language
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[SdkVersion]:
        stmt = (
            self._base_select()
            .where(SdkVersion.organization_id == organization_id)
            .order_by(SdkVersion.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_with_planned_deprecation(self, organization_id: UUID) -> Sequence[SdkVersion]:
        """Every still-enabled version that has a planned
        ``deprecated_at`` date set -- the ones the deprecation sweep
        needs to watch."""
        stmt = self._base_select().where(
            SdkVersion.organization_id == organization_id,
            SdkVersion.is_enabled.is_(True),
            SdkVersion.deprecated_at.is_not(None),
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SdkVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class SdkLanguageCatalogRepository(BaseRepository[SdkLanguageCatalog]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkLanguageCatalog, tenant_scope=tenant_scope)

    async def find_by_language(
        self, organization_id: UUID, *, language: SdkLanguage
    ) -> SdkLanguageCatalog | None:
        stmt = self._base_select().where(
            SdkLanguageCatalog.organization_id == organization_id,
            SdkLanguageCatalog.language == language,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(self, organization_id: UUID) -> Sequence[SdkLanguageCatalog]:
        stmt = self._base_select().where(
            SdkLanguageCatalog.organization_id == organization_id,
            SdkLanguageCatalog.is_enabled.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(self, organization_id: UUID) -> Sequence[SdkLanguageCatalog]:
        stmt = self._base_select().where(SdkLanguageCatalog.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class SdkPackageRepository(BaseRepository[SdkPackage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkPackage, tenant_scope=tenant_scope)

    async def list_for_version(self, sdk_version_id: UUID) -> Sequence[SdkPackage]:
        stmt = self._base_select().where(SdkPackage.sdk_version_id == sdk_version_id)
        return (await self._session.execute(stmt)).scalars().all()


class SdkDownloadRepository(BaseRepository[SdkDownload]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkDownload, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[SdkDownload]:
        stmt = (
            self._base_select()
            .where(SdkDownload.organization_id == organization_id)
            .order_by(SdkDownload.downloaded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_since(self, organization_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            SdkDownload.organization_id == organization_id, SdkDownload.downloaded_at >= since
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def count_for_version_since(self, sdk_version_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            SdkDownload.sdk_version_id == sdk_version_id, SdkDownload.downloaded_at >= since
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SdkDownload.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class SdkReleaseRepository(BaseRepository[SdkRelease]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkRelease, tenant_scope=tenant_scope)

    async def list_for_version(self, sdk_version_id: UUID) -> Sequence[SdkRelease]:
        stmt = self._base_select().where(SdkRelease.sdk_version_id == sdk_version_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, status: ReleaseStatus | None = None, limit: int = 100
    ) -> Sequence[SdkRelease]:
        stmt = self._base_select().where(SdkRelease.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(SdkRelease.status == status)
        stmt = stmt.order_by(SdkRelease.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: ReleaseStatus
    ) -> Sequence[SdkRelease]:
        stmt = self._base_select().where(
            SdkRelease.organization_id == organization_id, SdkRelease.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SdkRelease.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "SdkDownloadRepository",
    "SdkLanguageCatalogRepository",
    "SdkPackageRepository",
    "SdkReleaseRepository",
    "SdkVersionRepository",
]
