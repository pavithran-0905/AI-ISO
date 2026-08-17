"""SBOM catalog entries and signed release artifacts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.supply_chain import SbomCatalog, SignedArtifact
from app.repositories.supply_chain import SbomCatalogRepository, SignedArtifactRepository


class SbomCatalogService:
    def __init__(self, repo: SbomCatalogRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        component_name: str,
        component_version: str = "",
        license: str = "",
        generated_at: datetime,
    ) -> SbomCatalog:
        return await self._repo.create(
            SbomCatalog(
                organization_id=organization_id,
                component_name=component_name,
                component_version=component_version,
                license=license,
                generated_at=generated_at,
            )
        )


class SignedArtifactService:
    def __init__(self, repo: SignedArtifactRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        artifact_name: str,
        signature: str,
        artifact_version: str = "",
        is_verified: bool = False,
        signed_at: datetime,
    ) -> SignedArtifact:
        return await self._repo.create(
            SignedArtifact(
                organization_id=organization_id,
                artifact_name=artifact_name,
                artifact_version=artifact_version,
                signature=signature,
                is_verified=is_verified,
                signed_at=signed_at,
            )
        )


__all__ = ["SbomCatalogService", "SignedArtifactService"]
