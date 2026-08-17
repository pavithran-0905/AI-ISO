"""Artifact checksums, signatures, and SBOM publications -- the
supply-chain integrity records this service enforces."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ChecksumAlgorithm


class ArtifactChecksum(BaseModel):
    """``artifact_checksums`` -- one computed checksum for a release
    artifact."""

    __tablename__ = "artifact_checksums"
    __table_args__ = (Index("ix_artifact_checksum_artifact", "release_artifact_id"),)

    release_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_artifacts.id", ondelete="CASCADE"), index=True
    )
    algorithm: Mapped[ChecksumAlgorithm] = mapped_column(String(8), index=True)
    checksum_value: Mapped[str] = mapped_column(String(128))


class ArtifactSignature(BaseModel):
    """``artifact_signatures`` -- one digital signature for a release
    artifact."""

    __tablename__ = "artifact_signatures"
    __table_args__ = (Index("ix_artifact_signature_artifact", "release_artifact_id"),)

    release_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_artifacts.id", ondelete="CASCADE"), index=True
    )
    signature: Mapped[str] = mapped_column(Text)
    signer_identity: Mapped[str] = mapped_column(String(128), default="")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SbomPublication(BaseModel):
    """``sbom_publications`` -- one published software bill of
    materials for a release version."""

    __tablename__ = "sbom_publications"
    __table_args__ = (Index("ix_sbom_publication_version", "release_version_id"),)

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    component_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_uri: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["ArtifactChecksum", "ArtifactSignature", "SbomPublication"]
