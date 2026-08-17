"""Every enum this service's models and engines use (docs/080)."""

from __future__ import annotations

from enum import StrEnum


class ReleaseChannelType(StrEnum):
    """Which distribution channel a release version belongs to."""

    DEVELOPMENT = "development"
    NIGHTLY = "nightly"
    ALPHA = "alpha"
    BETA = "beta"
    RELEASE_CANDIDATE = "release_candidate"
    STABLE = "stable"
    LTS = "lts"
    CANARY = "canary"
    OEM = "oem"
    PRIVATE_ENTERPRISE = "private_enterprise"
    REGIONAL = "regional"
    CUSTOMER_SPECIFIC = "customer_specific"


class ReleaseStatus(StrEnum):
    """The shared release lifecycle every release version drives
    through -- see ``app.release.engine``."""

    DRAFT = "draft"
    VALIDATED = "validated"
    SIGNED = "signed"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class BuildStatus(StrEnum):
    """The shared job lifecycle every release build drives through --
    see ``app.release_build.engine``."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ArtifactType(StrEnum):
    """What kind of release artifact a package contains."""

    PLATFORM = "platform"
    BACKEND = "backend"
    FRONTEND = "frontend"
    CLI = "cli"
    SDK = "sdk"
    PLUGIN = "plugin"
    CONTAINER_IMAGE = "container_image"
    HELM_CHART = "helm_chart"
    KUBERNETES_MANIFEST = "kubernetes_manifest"
    DOCKER_COMPOSE = "docker_compose"
    OFFLINE_BUNDLE = "offline_bundle"
    EDGE_PACKAGE = "edge_package"
    CLOUD_PACKAGE = "cloud_package"
    DOCUMENTATION = "documentation"
    API_SPECIFICATION = "api_specification"
    DATABASE_MIGRATION = "database_migration"


class PackageFormat(StrEnum):
    """The on-disk format a release package is built as."""

    ZIP = "zip"
    TAR_GZ = "tar_gz"
    OCI_IMAGE = "oci_image"
    HELM_CHART = "helm_chart"
    PYTHON_PACKAGE = "python_package"
    NODE_PACKAGE = "node_package"
    STANDALONE_INSTALLER = "standalone_installer"
    OFFLINE_ARCHIVE = "offline_archive"
    ENTERPRISE_BUNDLE = "enterprise_bundle"


class PromotionStatus(StrEnum):
    """Where a release promotion stands in its own approval
    lifecycle."""

    PENDING = "pending"
    APPROVED = "approved"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class DistributionType(StrEnum):
    """How a release is distributed to its own targets."""

    GLOBAL = "global"
    REGIONAL = "regional"
    AIR_GAPPED = "air_gapped"
    PRIVATE_REPOSITORY = "private_repository"
    OEM = "oem"
    CUSTOMER_SPECIFIC = "customer_specific"
    MIRROR = "mirror"
    OFFLINE_EXPORT = "offline_export"


class DistributionStatus(StrEnum):
    """Where a release distribution stands."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ChecksumAlgorithm(StrEnum):
    """Which hashing algorithm an artifact checksum was computed
    with."""

    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"


class ReleaseNoteType(StrEnum):
    """What kind of change a release note entry documents."""

    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    BUG_FIX = "bug_fix"
    SECURITY_FIX = "security_fix"
    BREAKING_CHANGE = "breaking_change"
    MIGRATION_NOTE = "migration_note"
    UPGRADE_INSTRUCTION = "upgrade_instruction"
    KNOWN_ISSUE = "known_issue"
    RESOLVED_ISSUE = "resolved_issue"


class ReleaseReportKind(StrEnum):
    """What a generated report covers."""

    RELEASE = "release"
    ARTIFACT = "artifact"
    PROMOTION = "promotion"
    DISTRIBUTION = "distribution"
    DOWNLOAD = "download"
    LTS = "lts"
    EOL = "eol"
    EXECUTIVE = "executive"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    """The file format a generated report is rendered as."""

    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    HTML = "html"


class ReportStatus(StrEnum):
    """Where a report generation stands."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReleaseAuditAction(StrEnum):
    """What was done, for the immutable release audit trail."""

    RELEASE_CREATION = "release_creation"
    SIGNING_OPERATION = "signing_operation"
    PROMOTION_DECISION = "promotion_decision"
    DISTRIBUTION_EVENT = "distribution_event"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "ArtifactType",
    "BuildStatus",
    "ChecksumAlgorithm",
    "DistributionStatus",
    "DistributionType",
    "PackageFormat",
    "PromotionStatus",
    "ReleaseAuditAction",
    "ReleaseChannelType",
    "ReleaseNoteType",
    "ReleaseReportKind",
    "ReleaseStatus",
    "ReportFormat",
    "ReportStatus",
]
