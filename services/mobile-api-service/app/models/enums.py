"""Enumerations for the Mobile API service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself. See
``services/sdk-cli-service``'s own hard-won lesson (Prompt 071) on why
``is`` comparison, and even bare ``.value`` access, on such a value is
unsafe -- coerce through the enum class first (``EnumClass(value)``).
"""

from __future__ import annotations

from enum import StrEnum


class MobilePlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    FLUTTER = "flutter"
    REACT_NATIVE = "react_native"
    PWA = "pwa"
    OTHER = "other"


class DeviceTrustStatus(StrEnum):
    """A device's position in its own trust lifecycle -- see
    ``app.devices.engine`` for the transition table this drives."""

    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"


class SessionStatus(StrEnum):
    """A mobile session's position in its own lifecycle -- see
    ``app.authentication.engine`` for the transition table this drives."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class MobileAuthMethod(StrEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    JWT = "jwt"
    BIOMETRIC = "biometric"
    DEVICE_TRUST = "device_trust"
    CERTIFICATE = "certificate"
    SSO = "sso"
    OFFLINE = "offline"


class TokenStatus(StrEnum):
    """A device-bound mobile token's position in its own lifecycle."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SyncType(StrEnum):
    INCREMENTAL = "incremental"
    DELTA = "delta"
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    CONFIGURATION = "configuration"
    PROFILE = "profile"
    NOTIFICATION = "notification"
    ASSET = "asset"


class SyncJobStatus(StrEnum):
    """A sync job's position in its own lifecycle -- see
    ``app.sync.engine`` for the transition table this drives."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncQueueStatus(StrEnum):
    """One queued offline action's position in its own lifecycle -- see
    ``app.sync.engine`` for the transition table this drives."""

    QUEUED = "queued"
    PROCESSING = "processing"
    APPLIED = "applied"
    CONFLICT = "conflict"
    FAILED = "failed"


class ConflictResolutionStrategy(StrEnum):
    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"
    MANUAL = "manual"


class PushPlatform(StrEnum):
    FCM = "fcm"
    APNS = "apns"


class PushTokenStatus(StrEnum):
    ACTIVE = "active"
    INVALID = "invalid"
    REVOKED = "revoked"


class NotificationDeliveryStatus(StrEnum):
    """One push notification's position in its own delivery lifecycle
    -- see ``app.push.engine`` for the transition table this drives."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class ReleaseChannel(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    CANARY = "canary"


class TelemetryMetricType(StrEnum):
    APP_START = "app_start"
    API_PERFORMANCE = "api_performance"
    CRASH = "crash"
    SYNC_METRICS = "sync_metrics"
    NETWORK_QUALITY = "network_quality"
    BATTERY = "battery"
    DEVICE_HEALTH = "device_health"
    STORAGE = "storage"
    LATENCY = "latency"


class AnalyticsMetricType(StrEnum):
    DAILY_ACTIVE_USERS = "daily_active_users"
    MONTHLY_ACTIVE_USERS = "monthly_active_users"
    SESSION_DURATION = "session_duration"
    FEATURE_USAGE = "feature_usage"
    SCREEN_USAGE = "screen_usage"
    NOTIFICATION_ENGAGEMENT = "notification_engagement"
    OFFLINE_USAGE = "offline_usage"
    SYNC_STATISTICS = "sync_statistics"
    CRASH_STATISTICS = "crash_statistics"


class QrPurpose(StrEnum):
    DEVICE_ENROLLMENT = "device_enrollment"
    ORGANIZATION_JOIN = "organization_join"
    PROJECT_JOIN = "project_join"
    AUTHENTICATION_BOOTSTRAP = "authentication_bootstrap"
    CONFIGURATION_IMPORT = "configuration_import"


class DeepLinkCategory(StrEnum):
    UNIVERSAL = "universal"
    APP = "app"
    NOTIFICATION = "notification"
    RESOURCE = "resource"
    WORKFLOW = "workflow"
    APPROVAL = "approval"
    REPORT = "report"


class ReportKind(StrEnum):
    DEVICE = "device"
    SESSION = "session"
    NOTIFICATION = "notification"
    USAGE = "usage"
    SYNCHRONIZATION = "synchronization"
    SECURITY = "security"
    ANALYTICS = "analytics"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class MobileAuditAction(StrEnum):
    """What was done, for the immutable mobile audit trail."""

    DEVICE_REGISTRATION = "device_registration"
    AUTHENTICATION = "authentication"
    CONFIGURATION_CHANGE = "configuration_change"
    SYNCHRONIZATION = "synchronization"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AnalyticsMetricType",
    "ConflictResolutionStrategy",
    "DeepLinkCategory",
    "DeviceTrustStatus",
    "MobileAuditAction",
    "MobileAuthMethod",
    "MobilePlatform",
    "NotificationDeliveryStatus",
    "PushPlatform",
    "PushTokenStatus",
    "QrPurpose",
    "ReleaseChannel",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SessionStatus",
    "SyncJobStatus",
    "SyncQueueStatus",
    "SyncType",
    "TelemetryMetricType",
    "TokenStatus",
]
