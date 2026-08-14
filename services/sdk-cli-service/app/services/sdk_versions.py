"""SDK language catalog, version registration, packages, and download
recording.

Publishes ``SDKDownloaded`` on every recorded download.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import SdkDownloadedEvent
from app.models.enums import DistributionChannel, SdkLanguage
from app.models.sdk import SdkDownload, SdkLanguageCatalog, SdkPackage, SdkVersion
from app.repositories.sdk import (
    SdkDownloadRepository,
    SdkLanguageCatalogRepository,
    SdkPackageRepository,
    SdkVersionRepository,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SdkVersionService:
    def __init__(self, repo: SdkVersionRepository) -> None:
        self._repo = repo

    async def create_version(
        self,
        organization_id: UUID,
        *,
        language: SdkLanguage,
        version: str,
        api_compatibility_version: str,
    ) -> SdkVersion:
        return await self._repo.create(
            SdkVersion(
                organization_id=organization_id,
                language=language,
                version_label=version,
                api_compatibility_version=api_compatibility_version,
            )
        )

    async def deprecate(self, sdk_version: SdkVersion, *, now: datetime) -> SdkVersion:
        sdk_version.deprecated_at = now
        return await self._repo.update(sdk_version)


class SdkLanguageCatalogService:
    def __init__(self, repo: SdkLanguageCatalogRepository) -> None:
        self._repo = repo

    async def register_language(
        self, organization_id: UUID, *, language: SdkLanguage, display_name: str
    ) -> SdkLanguageCatalog:
        existing = await self._repo.find_by_language(organization_id, language=language)
        if existing is not None:
            return existing
        return await self._repo.create(
            SdkLanguageCatalog(
                organization_id=organization_id, language=language, display_name=display_name
            )
        )

    async def set_latest_version(
        self, catalog_entry: SdkLanguageCatalog, *, sdk_version_id: UUID
    ) -> SdkLanguageCatalog:
        catalog_entry.latest_version_id = sdk_version_id
        return await self._repo.update(catalog_entry)


class SdkPackageService:
    def __init__(self, repo: SdkPackageRepository) -> None:
        self._repo = repo

    async def add_package(
        self,
        organization_id: UUID,
        *,
        sdk_version_id: UUID,
        distribution_channel: DistributionChannel,
        package_ref: str,
        checksum_sha256: str,
        is_signed: bool = False,
    ) -> SdkPackage:
        return await self._repo.create(
            SdkPackage(
                organization_id=organization_id,
                sdk_version_id=sdk_version_id,
                distribution_channel=distribution_channel,
                package_ref=package_ref,
                checksum_sha256=checksum_sha256,
                is_signed=is_signed,
            )
        )


class SdkDownloadService:
    def __init__(
        self, repo: SdkDownloadRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def record_download(
        self,
        organization_id: UUID,
        *,
        sdk_version_id: UUID,
        language: SdkLanguage,
        now: datetime,
        source_ip: str | None = None,
    ) -> SdkDownload:
        download = await self._repo.create(
            SdkDownload(
                organization_id=organization_id,
                sdk_version_id=sdk_version_id,
                downloaded_at=now,
                source_ip=source_ip,
            )
        )
        await self._publish(
            SdkDownloadedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"sdk_version_id": str(sdk_version_id), "language": language.value},
            )
        )
        return download


__all__ = [
    "SdkDownloadService",
    "SdkLanguageCatalogService",
    "SdkPackageService",
    "SdkVersionService",
]
