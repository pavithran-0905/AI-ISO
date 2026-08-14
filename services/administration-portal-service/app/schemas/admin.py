"""Request/response schemas for the 16 docs/070 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    FeatureFlagScope,
    HealthCheckStatus,
    JobPriority,
    JobStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    TenantStatus,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class PageInfo(_Base):
    has_more: bool = False


# ---- dashboard --------------------------------------------------------------------------------


class DashboardResponse(_Base):
    tenant_count: int
    active_tenant_count: int
    organization_count: int
    running_job_count: int
    failed_job_count: int
    open_maintenance_window_count: int
    overall_health: HealthCheckStatus


# ---- settings ------------------------------------------------------------------------------


class SettingUpsertRequest(_Base):
    key: str
    value: dict[str, object]
    description: str | None = None


class SettingResponse(_Base):
    id: UUID
    key: str
    value: dict[str, object]
    description: str | None


class SettingsResponse(_Base):
    settings: list[SettingResponse]
    total: int


# ---- tenants -------------------------------------------------------------------------------


class TenantCreateRequest(_Base):
    organization_ref_id: UUID
    name: str


class TenantUpdateRequest(_Base):
    target_status: TenantStatus


class TenantResponse(_Base):
    id: UUID
    organization_ref_id: UUID
    name: str
    status: TenantStatus
    isolation_key: str | None


class TenantsResponse(_Base):
    tenants: list[TenantResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- feature flags -------------------------------------------------------------------------------


class FeatureFlagCreateRequest(_Base):
    name: str
    scope: FeatureFlagScope
    target_ref: str | None = None
    rollout_percentage: float = 100.0


class FeatureFlagUpdateRequest(_Base):
    is_enabled: bool | None = None
    is_killed: bool | None = None
    rollout_percentage: float | None = None


class FeatureFlagResponse(_Base):
    id: UUID
    name: str
    scope: FeatureFlagScope
    target_ref: str | None
    is_enabled: bool
    is_killed: bool
    rollout_percentage: float


class FeatureFlagsResponse(_Base):
    feature_flags: list[FeatureFlagResponse]
    total: int


# ---- jobs -------------------------------------------------------------------------------


class JobCreateRequest(_Base):
    job_key: str
    priority: JobPriority = JobPriority.NORMAL
    payload: dict[str, object] = Field(default_factory=dict)
    max_attempts: int = 3


class JobResponse(_Base):
    id: UUID
    job_key: str
    status: JobStatus
    priority: JobPriority
    attempt_count: int
    max_attempts: int
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobsResponse(_Base):
    jobs: list[JobResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- diagnostics / health --------------------------------------------------------------------


class DiagnosticResponse(_Base):
    id: UUID
    category: str
    status: HealthCheckStatus
    latency_ms: float | None
    ran_at: datetime


class DiagnosticsResponse(_Base):
    diagnostics: list[DiagnosticResponse]
    total: int


class HealthCheckComponentResponse(_Base):
    component: str
    status: HealthCheckStatus
    checked_at: datetime


class PlatformHealthResponse(_Base):
    overall_status: HealthCheckStatus
    components: list[HealthCheckComponentResponse]


# ---- statistics / reports --------------------------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    tenant_count: int
    user_count: int
    api_request_count: int
    background_job_count: int
    security_event_count: int
    platform_availability_fraction: float | None


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
    "DashboardResponse",
    "DiagnosticResponse",
    "DiagnosticsResponse",
    "FeatureFlagCreateRequest",
    "FeatureFlagResponse",
    "FeatureFlagUpdateRequest",
    "FeatureFlagsResponse",
    "HealthCheckComponentResponse",
    "JobCreateRequest",
    "JobResponse",
    "JobsResponse",
    "PageInfo",
    "PlatformHealthResponse",
    "ReportResponse",
    "ReportsResponse",
    "SettingResponse",
    "SettingUpsertRequest",
    "SettingsResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "TenantCreateRequest",
    "TenantResponse",
    "TenantUpdateRequest",
    "TenantsResponse",
]
