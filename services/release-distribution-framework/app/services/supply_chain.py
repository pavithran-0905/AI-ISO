"""Artifact checksums, signatures, and SBOM publications.

**Checksums are computed here, genuinely** (see
``app.signing.engine.compute_checksum``) since hashing bytes this
process already holds is real, executable work. **Signatures are
caller-supplied**, since producing one needs a private signing key
this service never holds -- the same caller-reported-outcome boundary
``services/production-hardening-framework``'s own supply-chain
services draw (Prompt 079).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import ChecksumAlgorithm
from app.models.supply_chain import ArtifactChecksum, ArtifactSignature, SbomPublication
from app.repositories.supply_chain import (
    ArtifactChecksumRepository,
    ArtifactSignatureRepository,
    SbomPublicationRepository,
)
from app.signing.engine import compute_checksum


class ArtifactChecksumService:
    def __init__(self, repo: ArtifactChecksumRepository) -> None:
        self._repo = repo

    async def compute_and_record(
        self,
        organization_id: UUID,
        *,
        release_artifact_id: UUID,
        data: bytes,
        algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256,
    ) -> ArtifactChecksum:
        checksum_value = compute_checksum(data, algorithm=algorithm)
        return await self._repo.create(
            ArtifactChecksum(
                organization_id=organization_id,
                release_artifact_id=release_artifact_id,
                algorithm=algorithm,
                checksum_value=checksum_value,
            )
        )


class ArtifactSignatureService:
    def __init__(self, repo: ArtifactSignatureRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        release_artifact_id: UUID,
        signature: str,
        signer_identity: str = "",
        is_verified: bool = False,
        signed_at: datetime,
    ) -> ArtifactSignature:
        return await self._repo.create(
            ArtifactSignature(
                organization_id=organization_id,
                release_artifact_id=release_artifact_id,
                signature=signature,
                signer_identity=signer_identity,
                is_verified=is_verified,
                signed_at=signed_at,
            )
        )


class SbomPublicationService:
    def __init__(self, repo: SbomPublicationRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        component_count: int,
        storage_uri: str = "",
        published_at: datetime,
    ) -> SbomPublication:
        return await self._repo.create(
            SbomPublication(
                organization_id=organization_id,
                release_version_id=release_version_id,
                component_count=component_count,
                storage_uri=storage_uri,
                published_at=published_at,
            )
        )


__all__ = ["ArtifactChecksumService", "ArtifactSignatureService", "SbomPublicationService"]
