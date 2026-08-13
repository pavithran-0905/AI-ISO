"""Request/response schemas for the 12 docs/065 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    BackupJobStatus,
    BackupType,
    ComplianceStatus,
    DrPlanStatus,
    DrTestKind,
    DrTestStatus,
    FailoverKind,
    FailoverStatus,
    RecoveryPriority,
    ReportFormat,
    ReportKind,
    ReportStatus,
    RestoreJobStatus,
    RestoreKind,
    ScheduleFrequency,
    SnapshotKind,
    SnapshotStatus,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class PageInfo(_Base):
    has_more: bool = False


# ---- jobs -------------------------------------------------------------------------------


class JobCreateRequest(_Base):
    target_id: UUID
    backup_type: BackupType
    schedule_id: UUID | None = None
    parent_job_id: UUID | None = None


class JobResponse(_Base):
    id: UUID
    target_id: UUID
    schedule_id: UUID | None
    parent_job_id: UUID | None
    backup_type: BackupType
    status: BackupJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: float | None
    size_bytes: int | None
    checksum: str | None
    error_message: str | None


class JobsResponse(_Base):
    jobs: list[JobResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- schedules --------------------------------------------------------------------------


class ScheduleCreateRequest(_Base):
    target_id: UUID
    backup_type: BackupType
    frequency: ScheduleFrequency
    cron_expression: str | None = None
    retention_days: int = Field(default=90, ge=1)


class ScheduleResponse(_Base):
    id: UUID
    target_id: UUID
    backup_type: BackupType
    frequency: ScheduleFrequency
    cron_expression: str | None
    is_enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    retention_days: int


class SchedulesResponse(_Base):
    schedules: list[ScheduleResponse]
    total: int


# ---- snapshots ----------------------------------------------------------------------------


class SnapshotResponse(_Base):
    id: UUID
    target_id: UUID
    snapshot_kind: SnapshotKind
    status: SnapshotStatus
    size_bytes: int | None
    created_at_source: datetime
    expires_at: datetime | None
    is_validated: bool


class SnapshotsResponse(_Base):
    snapshots: list[SnapshotResponse]
    total: int


# ---- restore ------------------------------------------------------------------------------


class RestoreRequest(_Base):
    target_id: UUID
    restore_kind: RestoreKind
    requested_at: datetime
    target_ref: str | None = None
    is_preview: bool = True


class RestoreResponse(_Base):
    restore_job_id: UUID | None
    status: RestoreJobStatus | None
    is_preview: bool
    selected_point_at: datetime | None
    refusal: str | None
    detail: str


# ---- failover / failback -------------------------------------------------------------------


class HealthCheckInput(_Base):
    check_name: str
    is_healthy: bool
    detail: str = ""


class FailoverRequest(_Base):
    dr_plan_id: UUID | None = None
    kind: FailoverKind
    source_ref: str | None = None
    target_ref: str | None = None
    health_checks: list[HealthCheckInput] = Field(default_factory=list)


class FailoverResponse(_Base):
    failover_event_id: UUID | None
    is_authorized: bool
    refusal: str | None
    detail: str
    status: FailoverStatus | None


# ---- dr plans / dr tests --------------------------------------------------------------------


class DrPlanResponse(_Base):
    id: UUID
    name: str
    description: str | None
    status: DrPlanStatus
    priority: RecoveryPriority
    rpo_minutes: int
    rto_minutes: int
    is_active: bool
    last_tested_at: datetime | None


class DrPlansResponse(_Base):
    plans: list[DrPlanResponse]
    total: int


class DrTestRequest(_Base):
    dr_plan_id: UUID
    test_kind: DrTestKind
    achieved_rpo_minutes: float | None = None
    achieved_rto_minutes: float | None = None
    summary: str | None = None


class DrTestResponse(_Base):
    id: UUID
    dr_plan_id: UUID
    test_kind: DrTestKind
    status: DrTestStatus
    rpo_status: ComplianceStatus
    rto_status: ComplianceStatus
    achieved_rpo_minutes: float | None
    achieved_rto_minutes: float | None
    summary: str | None


# ---- statistics / reports ---------------------------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    jobs_completed: int
    jobs_failed: int
    bytes_backed_up: int
    restore_jobs_completed: int
    restore_jobs_failed: int
    rpo_compliant_count: int
    rpo_violated_count: int
    rto_compliant_count: int
    rto_violated_count: int


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
    "DrPlanResponse",
    "DrPlansResponse",
    "DrTestRequest",
    "DrTestResponse",
    "FailoverRequest",
    "FailoverResponse",
    "HealthCheckInput",
    "JobCreateRequest",
    "JobResponse",
    "JobsResponse",
    "PageInfo",
    "ReportResponse",
    "ReportsResponse",
    "RestoreRequest",
    "RestoreResponse",
    "ScheduleCreateRequest",
    "ScheduleResponse",
    "SchedulesResponse",
    "SnapshotResponse",
    "SnapshotsResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
]
