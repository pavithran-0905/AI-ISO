"""Enumerations for the Public API & Developer Platform.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself. See
``services/sdk-cli-service``'s and ``services/mobile-api-service``'s
own hard-won lessons on why ``is`` comparison, and even bare ``.value``
access, on such a value is unsafe -- coerce through the enum class
first (``EnumClass(value)``).
"""

from __future__ import annotations

from enum import StrEnum


class DeveloperAccountStatus(StrEnum):
    """A developer account's position in its own lifecycle -- see
    ``app.developers.engine`` for the transition table this drives."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class DeveloperOrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ApplicationStatus(StrEnum):
    """A developer application's position in its own lifecycle -- see
    ``app.applications.engine`` for the transition table this drives."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class CredentialStatus(StrEnum):
    """Shared lifecycle for application credentials, API keys, and
    personal access tokens -- see ``app.api_keys.engine`` for the
    transition table this drives."""

    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApiProductType(StrEnum):
    PUBLIC = "public"
    PREMIUM = "premium"
    PARTNER = "partner"
    INTERNAL = "internal"


class ApiProductStatus(StrEnum):
    """An API product's position in its own governance workflow -- see
    ``app.products.engine`` for the transition table this drives."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OAuthTokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class OAuthTokenStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OAuthGrantType(StrEnum):
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    DEVICE_CODE = "device_code"
    REFRESH_TOKEN = "refresh_token"


class ApiVersionStatus(StrEnum):
    """An API version's position in its own lifecycle -- see
    ``app.versioning.engine`` for the transition table this drives."""

    DRAFT = "draft"
    RELEASED = "released"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"


class QuotaType(StrEnum):
    API_CALLS = "api_calls"
    STORAGE = "storage"
    WEBHOOK = "webhook"
    STREAMING = "streaming"
    AI_TOKENS = "ai_tokens"
    AUTOMATION = "automation"


class QuotaResetPolicy(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SandboxStatus(StrEnum):
    ACTIVE = "active"
    RESET = "reset"


class MockType(StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"


class ReportKind(StrEnum):
    API_USAGE = "api_usage"
    DEVELOPER = "developer"
    APPLICATION = "application"
    QUOTA = "quota"
    PERFORMANCE = "performance"
    REVENUE = "revenue"
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


class DeveloperAuditAction(StrEnum):
    """What was done, for the immutable developer platform audit trail."""

    DEVELOPER_REGISTRATION = "developer_registration"
    APPLICATION_CHANGE = "application_change"
    CREDENTIAL_CHANGE = "credential_change"
    API_PUBLICATION = "api_publication"
    VERSION_RELEASE = "version_release"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "ApiProductStatus",
    "ApiProductType",
    "ApiVersionStatus",
    "ApplicationStatus",
    "CredentialStatus",
    "DeveloperAccountStatus",
    "DeveloperAuditAction",
    "DeveloperOrganizationStatus",
    "MockType",
    "OAuthGrantType",
    "OAuthTokenStatus",
    "OAuthTokenType",
    "QuotaResetPolicy",
    "QuotaType",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SandboxStatus",
    "SubscriptionStatus",
]
