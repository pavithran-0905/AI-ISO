"""Request/response shapes for the 10 docs/075 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CheckResultStatus,
    DeploymentJobStatus,
    DeploymentJobType,
    DeploymentReportKind,
    InstallationMode,
    InstallationSessionStatus,
    PreflightCheckType,
    VerificationCheckType,
)

MAX_PAGE_SIZE = 500


# ---- POST /install/start, GET /install/status ------------------------------------------------


class InstallStartRequest(BaseModel):
    mode: InstallationMode


class InstallationSessionResponse(BaseModel):
    id: UUID
    mode: InstallationMode
    status: InstallationSessionStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- POST /install/validate --------------------------------------------------------------


class PreflightValidateRequest(BaseModel):
    check_type: PreflightCheckType
    status: CheckResultStatus
    detail: str = Field(default="", max_length=2048)
    installation_session_id: UUID | None = None


class PreflightResultResponse(BaseModel):
    id: UUID
    check_type: PreflightCheckType
    status: CheckResultStatus
    detail: str
    checked_at: datetime


# ---- POST /deploy, GET /deploy/status ------------------------------------------------------


class DeployRequest(BaseModel):
    deployment_profile_id: UUID
    job_type: DeploymentJobType = DeploymentJobType.DEPLOY


class DeploymentJobResponse(BaseModel):
    id: UUID
    job_type: DeploymentJobType
    status: DeploymentJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str


# ---- POST /upgrade -----------------------------------------------------------------------


class UpgradeRequest(BaseModel):
    deployment_profile_id: UUID
    from_version: str = Field(min_length=1, max_length=32)
    to_version: str = Field(min_length=1, max_length=32)


class UpgradeHistoryResponse(BaseModel):
    id: UUID
    deployment_job_id: UUID
    from_version: str
    to_version: str
    status: DeploymentJobStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- POST /rollback ----------------------------------------------------------------------


class RollbackRequest(BaseModel):
    deployment_profile_id: UUID
    current_version: str = Field(min_length=1, max_length=32)
    target_version: str = Field(min_length=1, max_length=32)
    reason: str = Field(default="", max_length=1024)


class RollbackHistoryResponse(BaseModel):
    id: UUID
    deployment_job_id: UUID
    from_version: str
    to_version: str
    reason: str
    status: DeploymentJobStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- GET /verification --------------------------------------------------------------------


class VerificationResultResponse(BaseModel):
    id: UUID
    check_type: VerificationCheckType
    status: CheckResultStatus
    detail: str
    verified_at: datetime


class VerificationResultsResponse(BaseModel):
    results: list[VerificationResultResponse]
    total: int


# ---- GET /reports -------------------------------------------------------------------------


class ReportResponse(BaseModel):
    id: UUID
    kind: DeploymentReportKind
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
    installation_count: int
    deployment_count: int
    upgrade_count: int
    rollback_count: int
    validation_failure_count: int
    success_count: int
    failure_count: int


class StatisticsResponse(BaseModel):
    windows: list[StatisticWindowResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "DeployRequest",
    "DeploymentJobResponse",
    "InstallStartRequest",
    "InstallationSessionResponse",
    "PreflightResultResponse",
    "PreflightValidateRequest",
    "ReportResponse",
    "ReportsResponse",
    "RollbackHistoryResponse",
    "RollbackRequest",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "UpgradeHistoryResponse",
    "UpgradeRequest",
    "VerificationResultResponse",
    "VerificationResultsResponse",
]
