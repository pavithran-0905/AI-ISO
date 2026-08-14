"""SDK languages, versions, packages, downloads, and releases."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DistributionChannel, ReleaseStatus, SdkLanguage


class SdkVersion(BaseModel):
    """``sdk_versions`` -- one released or draft version of one
    language's SDK."""

    __tablename__ = "sdk_versions"
    __table_args__ = (
        Index("ix_sdk_version_language", "language"),
        Index("ix_sdk_version_label", "version_label"),
    )

    language: Mapped[SdkLanguage] = mapped_column(String(16), index=True)
    version_label: Mapped[str] = mapped_column(String(32), index=True)
    """Deliberately not named ``version`` -- that is already
    ``BaseEntityMixin``'s own reserved optimistic-locking column (a
    plain integer every ``BaseRepository.update()`` increments), and a
    domain-level version *string* silently colliding with it is exactly
    the class of defect ``services/edge-management-service`` found and
    documented in Prompt 067."""
    api_compatibility_version: Mapped[str] = mapped_column(String(32))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SdkLanguageCatalog(BaseModel):
    """``sdk_languages`` -- one supported SDK language's catalog entry."""

    __tablename__ = "sdk_languages"
    __table_args__ = (Index("ix_sdk_language_catalog_language", "language"),)

    language: Mapped[SdkLanguage] = mapped_column(String(16), index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    latest_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sdk_versions.id", ondelete="SET NULL"), default=None
    )


class SdkPackage(BaseModel):
    """``sdk_packages`` -- one distribution-channel artifact for an SDK
    version."""

    __tablename__ = "sdk_packages"
    __table_args__ = (Index("ix_sdk_package_sdk_version", "sdk_version_id"),)

    sdk_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sdk_versions.id", ondelete="CASCADE"), index=True
    )
    distribution_channel: Mapped[DistributionChannel] = mapped_column(String(16))
    package_ref: Mapped[str] = mapped_column(String(512))
    """The package's identity on its distribution channel -- a PyPI
    project name, an npm package name, a GitHub release asset URL."""
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)


class SdkDownload(BaseModel):
    """``sdk_downloads`` -- one raw download event."""

    __tablename__ = "sdk_downloads"
    __table_args__ = (
        Index("ix_sdk_download_sdk_version", "sdk_version_id"),
        Index("ix_sdk_download_downloaded_at", "downloaded_at"),
    )

    sdk_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sdk_versions.id", ondelete="CASCADE"), index=True
    )
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), default=None)


class SdkRelease(BaseModel):
    """``sdk_releases`` -- one publication record for an SDK version."""

    __tablename__ = "sdk_releases"
    __table_args__ = (
        Index("ix_sdk_release_sdk_version", "sdk_version_id"),
        Index("ix_sdk_release_status", "status"),
    )

    sdk_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sdk_versions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ReleaseStatus] = mapped_column(
        String(16), default=ReleaseStatus.DRAFT, index=True
    )
    release_notes: Mapped[str] = mapped_column(Text, default="")
    breaking_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["SdkDownload", "SdkLanguageCatalog", "SdkPackage", "SdkRelease", "SdkVersion"]
