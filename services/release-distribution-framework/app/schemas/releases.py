"""Request/response shapes for the 12 docs/080 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PromotionStatus, ReleaseChannelType, ReleaseReportKind, ReleaseStatus

MAX_PAGE_SIZE = 500


# ---- GET/POST /releases, GET /releases/{id} ---------------------------------------------


class ReleaseVersionRequest(BaseModel):
    version_label: str = Field(min_length=1, max_length=64)
    release_channel_id: UUID
    is_security_release: bool = False


class ReleaseVersionResponse(BaseModel):
    id: UUID
    version_label: str
    release_channel_id: UUID
    status: ReleaseStatus
    is_security_release: bool
    released_at: datetime | None


class ReleaseVersionsResponse(BaseModel):
    releases: list[ReleaseVersionResponse]
    total: int


# ---- POST /releases/promote --------------------------------------------------------------


class ReleasePromotionRequest(BaseModel):
    release_version_id: UUID
    to_channel_type: ReleaseChannelType
    approved_by: str = Field(default="", max_length=128)


class ReleasePromotionResponse(BaseModel):
    id: UUID
    release_version_id: UUID
    from_channel_type: ReleaseChannelType
    to_channel_type: ReleaseChannelType
    status: PromotionStatus
    promoted_at: datetime | None


# ---- POST /releases/publish --------------------------------------------------------------


class ReleasePublishRequest(BaseModel):
    release_version_id: UUID


# ---- GET /artifacts ---------------------------------------------------------------------


class ReleaseArtifactResponse(BaseModel):
    id: UUID
    release_package_id: UUID
    artifact_name: str
    storage_uri: str
    checksum_sha256: str
    is_signed: bool


class ReleaseArtifactsResponse(BaseModel):
    artifacts: list[ReleaseArtifactResponse]
    total: int


# ---- GET /downloads ---------------------------------------------------------------------


class DownloadStatisticResponse(BaseModel):
    id: UUID
    release_artifact_id: UUID
    region_code: str
    bytes_transferred: int
    downloaded_at: datetime


class DownloadStatisticsResponse(BaseModel):
    downloads: list[DownloadStatisticResponse]
    total: int


# ---- GET /channels ----------------------------------------------------------------------


class ReleaseChannelResponse(BaseModel):
    id: UUID
    name: str
    channel_type: ReleaseChannelType
    is_enabled: bool


class ReleaseChannelsResponse(BaseModel):
    channels: list[ReleaseChannelResponse]
    total: int


# ---- GET /lts ---------------------------------------------------------------------------


class LtsVersionResponse(BaseModel):
    id: UUID
    release_version_id: UUID
    support_ends_at: datetime
    is_active: bool


class LtsVersionsResponse(BaseModel):
    lts_versions: list[LtsVersionResponse]
    total: int


# ---- GET /eol ---------------------------------------------------------------------------


class EolScheduleResponse(BaseModel):
    id: UUID
    release_version_id: UUID
    eol_date: datetime
    migration_recommendation: str


class EolSchedulesResponse(BaseModel):
    schedules: list[EolScheduleResponse]
    total: int


# ---- GET /reports -----------------------------------------------------------------------


class ReleaseReportResponse(BaseModel):
    id: UUID
    kind: ReleaseReportKind
    report_format: str
    title: str
    status: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class ReleaseReportsResponse(BaseModel):
    reports: list[ReleaseReportResponse]
    total: int


# ---- GET /statistics --------------------------------------------------------------------


class ReleaseStatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    release_count: int
    promotion_count: int
    download_count: int
    avg_release_success_rate: float


class ReleaseStatisticsResponse(BaseModel):
    windows: list[ReleaseStatisticWindowResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "DownloadStatisticResponse",
    "DownloadStatisticsResponse",
    "EolScheduleResponse",
    "EolSchedulesResponse",
    "LtsVersionResponse",
    "LtsVersionsResponse",
    "ReleaseArtifactResponse",
    "ReleaseArtifactsResponse",
    "ReleaseChannelResponse",
    "ReleaseChannelsResponse",
    "ReleasePromotionRequest",
    "ReleasePromotionResponse",
    "ReleasePublishRequest",
    "ReleaseReportResponse",
    "ReleaseReportsResponse",
    "ReleaseStatisticWindowResponse",
    "ReleaseStatisticsResponse",
    "ReleaseVersionRequest",
    "ReleaseVersionResponse",
    "ReleaseVersionsResponse",
]
