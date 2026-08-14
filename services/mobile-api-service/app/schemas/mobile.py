"""Request/response shapes for the 13 docs/072 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    MobileAuthMethod,
    MobilePlatform,
    NotificationDeliveryStatus,
    PushPlatform,
    PushTokenStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SyncJobStatus,
    SyncType,
)

MAX_PAGE_SIZE = 500


# ---- POST /mobile/login, POST /mobile/logout --------------------------------------------------


class DeviceLoginRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)
    platform: MobilePlatform
    device_model: str | None = Field(default=None, max_length=128)
    os_version: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=32)
    auth_method: MobileAuthMethod
    is_jailbroken: bool = False
    is_rooted: bool = False


class LoginResponse(BaseModel):
    session_id: UUID
    device_id: UUID
    user_id: str
    auth_method: MobileAuthMethod
    is_new_device: bool
    issued_at: datetime
    expires_at: datetime
    mobile_token: str


class LogoutRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)


class LogoutResponse(BaseModel):
    session_id: UUID
    status: str


# ---- POST /mobile/register-device --------------------------------------------------------------


class DeviceRegisterRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)
    platform: MobilePlatform
    device_model: str | None = Field(default=None, max_length=128)
    os_version: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=32)


class DeviceResponse(BaseModel):
    id: UUID
    device_identifier: str
    platform: MobilePlatform
    trust_status: str
    device_model: str | None
    os_version: str | None
    app_version: str | None
    last_seen_at: datetime | None


# ---- GET/PUT /mobile/profile ---------------------------------------------------------------


class ProfileResponse(BaseModel):
    user_id: str
    display_name: str
    locale: str
    timezone: str
    preferences: dict[str, Any]


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    locale: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    preferences: dict[str, Any] | None = None


# ---- POST /mobile/sync -----------------------------------------------------------------------


class SyncItemRequest(BaseModel):
    action_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    client_updated_at: datetime


class SyncRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)
    sync_type: SyncType
    items: list[SyncItemRequest] = Field(default_factory=list, max_length=MAX_PAGE_SIZE)


class SyncResponse(BaseModel):
    sync_job_id: UUID
    device_id: UUID
    status: SyncJobStatus
    item_count: int


# ---- GET /mobile/configuration ----------------------------------------------------------------


class ConfigurationResponse(BaseModel):
    environment: str
    platform: MobilePlatform
    entries: dict[str, Any]


# ---- GET /mobile/notifications --------------------------------------------------------------


class NotificationResponse(BaseModel):
    id: UUID
    device_id: UUID
    title: str
    body: str
    category: str
    status: NotificationDeliveryStatus
    retry_count: int
    delivered_at: datetime | None
    read_at: datetime | None


class NotificationsResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int


# ---- POST /mobile/push/register --------------------------------------------------------------


class PushRegisterRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)
    platform: PushPlatform
    token_value: str = Field(min_length=1, max_length=512)


class PushTokenResponse(BaseModel):
    id: UUID
    device_id: UUID
    platform: PushPlatform
    status: PushTokenStatus
    registered_at: datetime


# ---- POST /mobile/qr/register ------------------------------------------------------------------


class QrRegisterRequest(BaseModel):
    qr_token: str = Field(min_length=1)
    device_identifier: str = Field(min_length=1, max_length=255)
    platform: MobilePlatform
    device_model: str | None = Field(default=None, max_length=128)
    os_version: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=32)


# ---- GET /mobile/version ------------------------------------------------------------------------


class VersionPolicyResponse(BaseModel):
    platform: MobilePlatform
    latest_version: str
    minimum_version: str
    recommended_version: str
    is_below_minimum: bool
    is_update_recommended: bool
    is_forced_upgrade: bool
    release_notes: str
    released_at: datetime


# ---- GET /mobile/statistics -------------------------------------------------------------------


class StatisticsResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    daily_active_users: int
    session_count: int
    average_session_duration_seconds: float
    crash_count: int
    crash_rate: float
    offline_usage_ratio: float
    notification_engagement_rate: float
    sync_success_rate: float


# ---- GET /mobile/reports ------------------------------------------------------------------------


class ReportResponse(BaseModel):
    id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: ReportStatus
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class ReportsResponse(BaseModel):
    reports: list[ReportResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "ConfigurationResponse",
    "DeviceLoginRequest",
    "DeviceRegisterRequest",
    "DeviceResponse",
    "LoginResponse",
    "LogoutRequest",
    "LogoutResponse",
    "NotificationResponse",
    "NotificationsResponse",
    "ProfileResponse",
    "ProfileUpdateRequest",
    "PushRegisterRequest",
    "PushTokenResponse",
    "QrRegisterRequest",
    "ReportResponse",
    "ReportsResponse",
    "StatisticsResponse",
    "SyncItemRequest",
    "SyncRequest",
    "SyncResponse",
    "VersionPolicyResponse",
]
