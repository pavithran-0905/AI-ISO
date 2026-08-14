"""Request/response schemas for the 13 docs/067 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    DeviceHealthStatus,
    DeviceLifecycleState,
    EdgeDeviceType,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SyncKind,
    SyncStatus,
    UpdateKind,
    UpdateStatus,
    UpdateStrategy,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class PageInfo(_Base):
    has_more: bool = False


# ---- sites ----------------------------------------------------------------------------------


class SiteCreateRequest(_Base):
    name: str
    business_unit: str | None = None
    description: str | None = None
    geo_latitude: float | None = None
    geo_longitude: float | None = None


class SiteResponse(_Base):
    id: UUID
    name: str
    business_unit: str | None
    description: str | None
    geo_latitude: float | None
    geo_longitude: float | None


class SitesResponse(_Base):
    sites: list[SiteResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- devices ----------------------------------------------------------------------------------


class DeviceCreateRequest(_Base):
    site_id: UUID
    name: str
    device_type: EdgeDeviceType
    credential_ref: str
    credential_expires_at: datetime | None = None
    gateway_id: UUID | None = None
    location_id: UUID | None = None
    serial_number: str | None = None


class DeviceUpdateRequest(_Base):
    location_id: UUID | None = None
    gateway_id: UUID | None = None
    ip_address: str | None = None
    is_schedulable: bool | None = None
    labels: dict[str, str] | None = None
    tags: list[str] | None = None
    description: str | None = None


class DeviceResponse(_Base):
    id: UUID
    site_id: UUID
    gateway_id: UUID | None
    location_id: UUID | None
    cluster_id: UUID | None
    name: str
    device_type: EdgeDeviceType
    lifecycle_state: DeviceLifecycleState
    health_status: DeviceHealthStatus
    serial_number: str | None
    firmware_version: str | None
    is_online: bool
    is_schedulable: bool
    registered_at: datetime | None
    last_seen_at: datetime | None


class DevicesResponse(_Base):
    devices: list[DeviceResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- provisioning / sync / update / remote access --------------------------------------------


class ProvisionRequest(_Base):
    target_state: DeviceLifecycleState


class SyncRequest(_Base):
    sync_kind: SyncKind = SyncKind.INCREMENTAL


class SyncResponse(_Base):
    sync_id: UUID
    device_id: UUID
    sync_kind: SyncKind
    status: SyncStatus
    duration_ms: float | None


class UpdateRequest(_Base):
    update_kind: UpdateKind = UpdateKind.FIRMWARE
    strategy: UpdateStrategy = UpdateStrategy.STAGED
    to_version: str


class UpdateResponse(_Base):
    update_id: UUID | None
    device_id: UUID
    to_version: str
    status: UpdateStatus | None
    refusal: str | None
    detail: str


class RemoteAccessRequest(_Base):
    reason: str


class RemoteAccessResponse(_Base):
    device_id: UUID
    granted: bool
    detail: str


# ---- health / statistics / reports -------------------------------------------------------------


class DeviceHealthResponse(_Base):
    device_id: UUID
    health_status: DeviceHealthStatus
    is_online: bool


class FleetHealthResponse(_Base):
    devices: list[DeviceHealthResponse]
    total: int


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    sites_registered: int
    devices_online: int
    devices_offline: int
    synchronizations_completed: int
    synchronizations_failed: int
    updates_completed: int
    updates_failed: int


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
    "DeviceCreateRequest",
    "DeviceHealthResponse",
    "DeviceResponse",
    "DeviceUpdateRequest",
    "DevicesResponse",
    "FleetHealthResponse",
    "PageInfo",
    "ProvisionRequest",
    "RemoteAccessRequest",
    "RemoteAccessResponse",
    "ReportResponse",
    "ReportsResponse",
    "SiteCreateRequest",
    "SiteResponse",
    "SitesResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "SyncRequest",
    "SyncResponse",
    "UpdateRequest",
    "UpdateResponse",
]
