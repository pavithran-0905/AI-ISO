"""Supply chain security -- the SBOM catalog and signed release
artifacts."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class SbomCatalog(BaseModel):
    """``sbom_catalog`` -- one component entry in a generated
    software bill of materials."""

    __tablename__ = "sbom_catalog"

    component_name: Mapped[str] = mapped_column(String(256), index=True)
    component_version: Mapped[str] = mapped_column(String(64), default="")
    license: Mapped[str] = mapped_column(String(128), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SignedArtifact(BaseModel):
    """``signed_artifacts`` -- one release artifact and its own
    signature verification state."""

    __tablename__ = "signed_artifacts"

    artifact_name: Mapped[str] = mapped_column(String(256), index=True)
    artifact_version: Mapped[str] = mapped_column(String(64), default="")
    signature: Mapped[str] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["SbomCatalog", "SignedArtifact"]
