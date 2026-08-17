"""Release packages and the individual artifacts within them."""

from __future__ import annotations

from uuid import UUID

from app.models.enums import ArtifactType, PackageFormat
from app.models.packages import ReleaseArtifact, ReleasePackage
from app.repositories.packages import ReleaseArtifactRepository, ReleasePackageRepository


class ReleasePackageService:
    def __init__(self, repo: ReleasePackageRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        artifact_type: ArtifactType,
        package_format: PackageFormat,
        name: str,
        size_bytes: int = 0,
    ) -> ReleasePackage:
        return await self._repo.create(
            ReleasePackage(
                organization_id=organization_id,
                release_version_id=release_version_id,
                artifact_type=artifact_type,
                package_format=package_format,
                name=name,
                size_bytes=size_bytes,
            )
        )


class ReleaseArtifactService:
    def __init__(self, repo: ReleaseArtifactRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        release_package_id: UUID,
        artifact_name: str,
        storage_uri: str = "",
        checksum_sha256: str = "",
        is_signed: bool = False,
    ) -> ReleaseArtifact:
        return await self._repo.create(
            ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=release_package_id,
                artifact_name=artifact_name,
                storage_uri=storage_uri,
                checksum_sha256=checksum_sha256,
                is_signed=is_signed,
            )
        )


__all__ = ["ReleaseArtifactService", "ReleasePackageService"]
