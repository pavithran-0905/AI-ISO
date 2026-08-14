"""Enumerations for the SDK & CLI service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself -- see
``services/multi-cluster-management-service``'s own hard-won lesson on
why ``is`` comparison against such a value is unsafe.
"""

from __future__ import annotations

from enum import StrEnum


class SdkLanguage(StrEnum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    DOTNET = "dotnet"


class DistributionChannel(StrEnum):
    PYPI = "pypi"
    NPM = "npm"
    MAVEN = "maven"
    NUGET = "nuget"
    GO_MODULES = "go_modules"
    GITHUB_RELEASES = "github_releases"
    OFFLINE = "offline"


class ReleaseStatus(StrEnum):
    """An SDK release's position in its own publication lifecycle --
    see ``app.sdk.engine`` for the transition table this drives."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    YANKED = "yanked"


class PluginStatus(StrEnum):
    """A CLI plugin's position in its own lifecycle -- see
    ``app.cli.plugins.engine`` for the transition table this drives."""

    AVAILABLE = "available"
    INSTALLED = "installed"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


class CliAuthMethod(StrEnum):
    USERNAME_PASSWORD = "username_password"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    API_KEY = "api_key"
    PERSONAL_ACCESS_TOKEN = "personal_access_token"
    DEVICE_FLOW = "device_flow"
    BROWSER_LOGIN = "browser_login"
    OFFLINE_TOKEN = "offline_token"


class CliUpdateStatus(StrEnum):
    """A CLI update attempt's position in its own lifecycle -- see
    ``app.cli.engine`` for the transition table this drives."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    APPLIED = "applied"
    FAILED = "failed"


class ReportKind(StrEnum):
    SDK = "sdk"
    CLI = "cli"
    USAGE = "usage"
    DOWNLOAD = "download"
    COMPATIBILITY = "compatibility"
    PLUGIN = "plugin"
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
    """What was done, for the immutable SDK/CLI audit trail."""

    SDK_RELEASED = "sdk_released"
    CLI_RELEASED = "cli_released"
    PLUGIN_MANAGEMENT = "plugin_management"
    AUTHENTICATION = "authentication"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AuditAction",
    "CliAuthMethod",
    "CliUpdateStatus",
    "DistributionChannel",
    "PluginStatus",
    "ReleaseStatus",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SdkLanguage",
]
