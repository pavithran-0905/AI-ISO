"""Release packages and the individual artifacts within them."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ArtifactType, PackageFormat


class ReleasePackage(BaseModel):
    """``release_packages`` -- one packaged artifact bundle for a
    release version."""

    __tablename__ = "release_packages"
    __table_args__ = (Index("ix_release_package_version", "release_version_id"),)

    release_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_versions.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(String(24), index=True)
    package_format: Mapped[PackageFormat] = mapped_column(String(24), index=True)
    name: Mapped[str] = mapped_column(String(256))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)


class ReleaseArtifact(BaseModel):
    """``release_artifacts`` -- one individual downloadable file
    within a release package."""

    __tablename__ = "release_artifacts"
    __table_args__ = (Index("ix_release_artifact_package", "release_package_id"),)

    release_package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("release_packages.id", ondelete="CASCADE"), index=True
    )
    artifact_name: Mapped[str] = mapped_column(String(256), index=True)
    storage_uri: Mapped[str] = mapped_column(Text, default="")
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="")
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = ["ReleaseArtifact", "ReleasePackage"]
