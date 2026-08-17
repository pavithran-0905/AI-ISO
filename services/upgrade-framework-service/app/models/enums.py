"""Enumerations for the Upgrade Framework service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself. Coerce through the enum
class first (``EnumClass(value)``) before comparing or reading
``.value`` on a row that may have just come back from a query.
"""

from __future__ import annotations

from enum import StrEnum


class ReleaseChannelType(StrEnum):
    STABLE = "stable"
    LTS = "lts"
    BETA = "beta"
    CANARY = "canary"
    DEVELOPMENT = "development"
    CUSTOM_ENTERPRISE = "custom_enterprise"
    REGIONAL = "regional"
    PRIVATE = "private"


class UpgradeTargetType(StrEnum):
    PLATFORM = "platform"
    PLATFORM_SERVICE = "platform_service"
    PLUGIN = "plugin"
    SDK = "sdk"
    CLI = "cli"
    EDGE_DEVICE = "edge_device"
    KUBERNETES_CLUSTER = "kubernetes_cluster"
    CLOUD_RESOURCE = "cloud_resource"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    AI_MODEL = "ai_model"
    KNOWLEDGE_BASE = "knowledge_base"


class UpgradeStrategy(StrEnum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ZERO_DOWNTIME = "zero_downtime"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    MAINTENANCE_WINDOW = "maintenance_window"
    MANUAL_APPROVAL = "manual_approval"


class UpgradeJobStatus(StrEnum):
    """The shared lifecycle for an upgrade job, a migration, a plugin
    migration, and a rollback attempt -- see ``app.upgrade.engine`` for
    the transition table this drives."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CheckResultStatus(StrEnum):
    """Shared pass/fail/warn outcome for dependency checks,
    compatibility matrix entries, and verification results."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class CompatibilityType(StrEnum):
    VERSION = "version"
    API = "api"
    SCHEMA = "schema"
    PLUGIN = "plugin"
    CONNECTOR = "connector"
    OPERATING_SYSTEM = "operating_system"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"
    DEPENDENCY = "dependency"


class MigrationType(StrEnum):
    DATABASE_SCHEMA = "database_schema"
    CONFIGURATION = "configuration"
    PLUGIN = "plugin"
    API = "api"
    DATA_TRANSFORMATION = "data_transformation"


class UpgradeTargetStatus(StrEnum):
    """Shared by ``upgrade_targets`` and ``upgrade_results`` -- a
    per-target outcome within a fleet upgrade job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationCheckType(StrEnum):
    HEALTH = "health"
    API = "api"
    DATABASE = "database"
    PERFORMANCE = "performance"
    SMOKE_TEST = "smoke_test"


class UpgradeReportKind(StrEnum):
    UPGRADE = "upgrade"
    COMPATIBILITY = "compatibility"
    MIGRATION = "migration"
    ROLLBACK = "rollback"
    RELEASE = "release"
    FLEET_UPGRADE = "fleet_upgrade"
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


class UpgradeAuditAction(StrEnum):
    """What was done, for the immutable upgrade audit trail."""

    UPGRADE_SCHEDULING = "upgrade_scheduling"
    UPGRADE_EXECUTION = "upgrade_execution"
    ROLLBACK = "rollback"
    MIGRATION_EXECUTION = "migration_execution"
    RELEASE_PUBLICATION = "release_publication"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "CheckResultStatus",
    "CompatibilityType",
    "MigrationType",
    "ReleaseChannelType",
    "ReportFormat",
    "ReportStatus",
    "UpgradeAuditAction",
    "UpgradeJobStatus",
    "UpgradeReportKind",
    "UpgradeStrategy",
    "UpgradeTargetStatus",
    "UpgradeTargetType",
    "VerificationCheckType",
]
