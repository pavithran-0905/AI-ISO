"""Request/response schemas for the 12 docs/071 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import (
    CliUpdateStatus,
    PluginStatus,
    ReleaseStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SdkLanguage,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


# ---- GET /sdk -----------------------------------------------------------------------------


class SdkLanguageResponse(_Base):
    id: UUID
    language: SdkLanguage
    display_name: str
    is_enabled: bool
    latest_version_id: UUID | None


class SdkResponse(_Base):
    languages: list[SdkLanguageResponse]
    total: int


# ---- GET /sdk/releases ---------------------------------------------------------------------


class SdkReleaseResponse(_Base):
    id: UUID
    sdk_version_id: UUID
    status: ReleaseStatus
    release_notes: str
    breaking_changes: bool
    published_at: datetime | None


class SdkReleasesResponse(_Base):
    releases: list[SdkReleaseResponse]
    total: int


# ---- GET /sdk/downloads ---------------------------------------------------------------------


class SdkDownloadResponse(_Base):
    id: UUID
    sdk_version_id: UUID
    downloaded_at: datetime
    source_ip: str | None


class SdkDownloadsResponse(_Base):
    downloads: list[SdkDownloadResponse]
    total: int


# ---- POST /sdk/generate ---------------------------------------------------------------------


class GeneratorFieldRequest(_Base):
    name: str
    type_name: str


class GeneratorModelRequest(_Base):
    class_name: str
    fields: list[GeneratorFieldRequest]


class SdkGenerateRequest(_Base):
    language: SdkLanguage
    version: str
    api_compatibility_version: str
    models: list[GeneratorModelRequest]
    release_notes: str = ""
    breaking_changes: bool = False


class GeneratedArtifactResponse(_Base):
    class_name: str
    source: str


class SdkGenerateResponse(_Base):
    sdk_version_id: UUID
    sdk_release_id: UUID
    artifacts: list[GeneratedArtifactResponse]


# ---- GET /cli, GET /cli/releases --------------------------------------------------------------


class CliVersionResponse(_Base):
    id: UUID
    version: str
    api_compatibility_version: str
    is_enabled: bool
    released_at: datetime | None
    deprecated_at: datetime | None


class CliVersionsResponse(_Base):
    versions: list[CliVersionResponse]
    total: int


# ---- POST /cli/update ---------------------------------------------------------------------


class CliUpdateRequest(_Base):
    from_version: str
    to_version: str
    succeeded: bool
    """Whether the update attempt succeeded -- reported by the caller;
    this service records the outcome, it never downloads or applies a
    real CLI binary itself. See this package's README "Scope
    boundary"."""


class CliUpdateResponse(_Base):
    id: UUID
    from_version: str
    to_version: str
    status: CliUpdateStatus
    checked_at: datetime
    applied_at: datetime | None


# ---- POST /cli/plugins/install, POST /cli/plugins/remove ------------------------------------


class PluginInstallRequest(_Base):
    name: str
    version: str
    checksum_sha256: str
    is_signed: bool = False
    marketplace_ref: str | None = None


class PluginRemoveRequest(_Base):
    name: str


class CliPluginResponse(_Base):
    id: UUID
    name: str
    version: str
    status: PluginStatus
    is_signed: bool
    marketplace_ref: str | None


# ---- statistics / reports -------------------------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    sdk_download_count: int
    cli_download_count: int
    command_execution_count: int
    plugin_install_count: int
    auth_success_count: int
    auth_failure_count: int


class StatisticsResponse(_Base):
    windows: list[StatisticWindowResponse]
    total: int


class ReportResponse(_Base):
    id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: ReportStatus
    period_start: datetime | None
    period_end: datetime | None
    generated_at: datetime | None
    row_count: int | None


class ReportsResponse(_Base):
    reports: list[ReportResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "CliPluginResponse",
    "CliUpdateRequest",
    "CliUpdateResponse",
    "CliVersionResponse",
    "CliVersionsResponse",
    "GeneratedArtifactResponse",
    "GeneratorFieldRequest",
    "GeneratorModelRequest",
    "PluginInstallRequest",
    "PluginRemoveRequest",
    "ReportResponse",
    "ReportsResponse",
    "SdkDownloadResponse",
    "SdkDownloadsResponse",
    "SdkGenerateRequest",
    "SdkGenerateResponse",
    "SdkLanguageResponse",
    "SdkReleaseResponse",
    "SdkReleasesResponse",
    "SdkResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
]
