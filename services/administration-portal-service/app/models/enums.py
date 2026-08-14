"""Enumerations for the administration portal service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every other
AI-IOS service's convention), and comparable with ``==`` against a value
freshly loaded from the database, which comes back as a plain ``str``
rather than the enum instance itself -- see
``services/multi-cluster-management-service``'s own hard-won lesson on
why ``is`` comparison against such a value is unsafe.
"""

from __future__ import annotations

from enum import StrEnum


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class TenantStatus(StrEnum):
    """A tenant's position in its own provisioning/operational
    lifecycle -- see ``app.tenants.engine`` for the transition table
    this drives."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    MIGRATING = "migrating"
    DELETING = "deleting"
    DELETED = "deleted"


class ProvisioningStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class FeatureFlagScope(StrEnum):
    GLOBAL = "global"
    TENANT = "tenant"
    ORGANIZATION = "organization"
    PROJECT = "project"


class JobStatus(StrEnum):
    """A background job's position in its own execution lifecycle --
    see ``app.jobs.engine`` for the transition table this drives."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class JobPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MaintenanceStatus(StrEnum):
    """A maintenance window's position in its own approval/execution
    lifecycle -- see ``app.maintenance.engine`` for the transition
    table this drives."""

    SCHEDULED = "scheduled"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaintenanceKind(StrEnum):
    ROUTINE = "routine"
    EMERGENCY = "emergency"
    ROLLING = "rolling"


class AnnouncementScope(StrEnum):
    GLOBAL = "global"
    TENANT = "tenant"


class ApiKeyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SecurityEventSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventKind(StrEnum):
    LOGIN_FAILURE = "login_failure"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"
    IP_BLOCKED = "ip_blocked"
    MFA_FAILURE = "mfa_failure"
    CONFIG_TAMPERING = "config_tampering"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class HealthCheckStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DiagnosticCategory(StrEnum):
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    API = "api"
    STORAGE = "storage"
    CLUSTER = "cluster"
    AI = "ai"
    CONNECTOR = "connector"
    PLUGIN = "plugin"


class ReportKind(StrEnum):
    TENANT = "tenant"
    PLATFORM = "platform"
    SECURITY = "security"
    API = "api"
    FEATURE = "feature"
    HEALTH = "health"
    OPERATIONAL = "operational"
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


class AuditAction(StrEnum):
    """What was done, for the immutable system audit trail."""

    ADMIN_LOGIN = "admin_login"
    CONFIGURATION_CHANGED = "configuration_changed"
    FEATURE_FLAG_CHANGED = "feature_flag_changed"
    TENANT_OPERATION = "tenant_operation"
    SECURITY_OPERATION = "security_operation"
    API_MANAGEMENT = "api_management"
    MAINTENANCE_OPERATION = "maintenance_operation"
    PLATFORM_ADMINISTRATION = "platform_administration"


__all__ = [
    "AnnouncementScope",
    "ApiKeyStatus",
    "AuditAction",
    "DiagnosticCategory",
    "FeatureFlagScope",
    "HealthCheckStatus",
    "JobPriority",
    "JobStatus",
    "MaintenanceKind",
    "MaintenanceStatus",
    "OrganizationStatus",
    "ProvisioningStatus",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SecurityEventKind",
    "SecurityEventSeverity",
    "TenantStatus",
]
