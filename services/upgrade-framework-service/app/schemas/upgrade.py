"""Request/response shapes for the 10 docs/076 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CheckResultStatus,
    CompatibilityType,
    ReleaseChannelType,
    UpgradeJobStatus,
    UpgradeReportKind,
)

MAX_PAGE_SIZE = 500


# ---- GET /releases -------------------------------------------------------------------------


class ReleaseVersionResponse(BaseModel):
    id: UUID
    release_channel_id: UUID
    version_label: str
    released_at: datetime
    is_current: bool


class ReleaseVersionsResponse(BaseModel):
    releases: list[ReleaseVersionResponse]
    total: int


# ---- GET /channels ------------------------------------------------------------------------


class ReleaseChannelResponse(BaseModel):
    id: UUID
    name: str
    channel_type: ReleaseChannelType
    is_enabled: bool


class ReleaseChannelsResponse(BaseModel):
    channels: list[ReleaseChannelResponse]
    total: int


# ---- POST /upgrade, GET /upgrade/jobs -----------------------------------------------------


class UpgradeRequest(BaseModel):
    upgrade_plan_id: UUID
    plan_name: str = Field(min_length=1, max_length=128)


class UpgradeJobResponse(BaseModel):
    id: UUID
    upgrade_plan_id: UUID
    status: UpgradeJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str


class UpgradeJobsResponse(BaseModel):
    jobs: list[UpgradeJobResponse]
    total: int


# ---- POST /upgrade/simulate ----------------------------------------------------------------


class SimulateRequest(BaseModel):
    compatibility_results: list[CheckResultStatus] = Field(default_factory=list)
    dependency_results: list[CheckResultStatus] = Field(default_factory=list)
    target_count: int = Field(ge=0, default=1)
    seconds_per_target: float = Field(ge=0.0, default=60.0)


class SimulationResponse(BaseModel):
    risk_level: str
    estimated_duration_seconds: float
    check_count: int


# ---- GET /upgrade/history -----------------------------------------------------------------


class UpgradeHistoryEntryResponse(BaseModel):
    id: UUID
    upgrade_job_id: UUID
    event_type: str
    detail: str
    occurred_at: datetime


class UpgradeHistoryListResponse(BaseModel):
    entries: list[UpgradeHistoryEntryResponse]
    total: int


# ---- POST /rollback -----------------------------------------------------------------------


class RollbackRequest(BaseModel):
    upgrade_plan_id: UUID
    current_version: str = Field(min_length=1, max_length=32)
    target_version: str = Field(min_length=1, max_length=32)
    reason: str = Field(default="", max_length=1024)


class RollbackHistoryResponse(BaseModel):
    id: UUID
    upgrade_job_id: UUID
    from_version: str
    to_version: str
    reason: str
    status: UpgradeJobStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- GET /compatibility -------------------------------------------------------------------


class CompatibilityEntryResponse(BaseModel):
    id: UUID
    from_version: str
    to_version: str
    compatibility_type: CompatibilityType
    status: CheckResultStatus
    detail: str


class CompatibilityEntriesResponse(BaseModel):
    entries: list[CompatibilityEntryResponse]
    total: int


# ---- GET /reports -------------------------------------------------------------------------


class ReportResponse(BaseModel):
    id: UUID
    kind: UpgradeReportKind
    report_format: str
    title: str
    status: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class ReportsResponse(BaseModel):
    reports: list[ReportResponse]
    total: int


# ---- GET /statistics -----------------------------------------------------------------------


class StatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    upgrade_count: int
    rollback_count: int
    migration_count: int
    compatibility_failure_count: int
    success_count: int
    failure_count: int


class StatisticsResponse(BaseModel):
    windows: list[StatisticWindowResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "CompatibilityEntriesResponse",
    "CompatibilityEntryResponse",
    "ReleaseChannelResponse",
    "ReleaseChannelsResponse",
    "ReleaseVersionResponse",
    "ReleaseVersionsResponse",
    "ReportResponse",
    "ReportsResponse",
    "RollbackHistoryResponse",
    "RollbackRequest",
    "SimulateRequest",
    "SimulationResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "UpgradeHistoryEntryResponse",
    "UpgradeHistoryListResponse",
    "UpgradeJobResponse",
    "UpgradeJobsResponse",
    "UpgradeRequest",
]
