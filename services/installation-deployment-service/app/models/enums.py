"""Enumerations for the Installation & Deployment service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself. See
``services/developer-portal-service``'s and every prior service's own
hard-won lessons on why ``is`` comparison, and even bare ``.value``
access, on such a value is unsafe -- coerce through the enum class
first (``EnumClass(value)``).
"""

from __future__ import annotations

from enum import StrEnum


class DeploymentTargetType(StrEnum):
    LOCAL_DEVELOPMENT = "local_development"
    DOCKER_COMPOSE = "docker_compose"
    SINGLE_NODE_KUBERNETES = "single_node_kubernetes"
    MULTI_NODE_KUBERNETES = "multi_node_kubernetes"
    OPENSHIFT = "openshift"
    BARE_METAL = "bare_metal"
    VIRTUAL_MACHINE = "virtual_machine"
    PRIVATE_CLOUD = "private_cloud"
    PUBLIC_CLOUD = "public_cloud"
    HYBRID_CLOUD = "hybrid_cloud"
    EDGE = "edge"
    AIR_GAPPED = "air_gapped"


class InstallationMode(StrEnum):
    INTERACTIVE_WIZARD = "interactive_wizard"
    CLI = "cli"
    API_DRIVEN = "api_driven"
    SILENT = "silent"
    HEADLESS = "headless"
    CICD = "cicd"
    OFFLINE = "offline"
    RECOVERY = "recovery"
    REPAIR = "repair"


class InstallationSessionStatus(StrEnum):
    """An installation session's own lifecycle -- see
    ``app.installer.engine`` for the transition table this drives."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DeploymentJobType(StrEnum):
    INSTALL = "install"
    DEPLOY = "deploy"
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"


class DeploymentJobStatus(StrEnum):
    """A deployment job's own lifecycle, shared by every job type -- see
    ``app.deployment.engine`` for the transition table this drives."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DeploymentEngine(StrEnum):
    HELM = "helm"
    DOCKER_COMPOSE = "docker_compose"
    KUBERNETES_MANIFEST = "kubernetes_manifest"
    OPENSHIFT = "openshift"


class DeploymentStrategy(StrEnum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    PARALLEL = "parallel"
    DEPENDENCY_AWARE = "dependency_aware"


class PreflightCheckType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    DISK_PERFORMANCE = "disk_performance"
    NETWORK_CONNECTIVITY = "network_connectivity"
    DNS = "dns"
    TIME_SYNCHRONIZATION = "time_synchronization"
    OPERATING_SYSTEM = "operating_system"
    CONTAINER_RUNTIME = "container_runtime"
    KUBERNETES = "kubernetes"
    OPENSHIFT = "openshift"
    DATABASE = "database"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    NEO4J = "neo4j"
    MINIO = "minio"
    TLS = "tls"
    CERTIFICATE = "certificate"
    PORT_AVAILABILITY = "port_availability"
    FIREWALL = "firewall"
    SELINUX = "selinux"
    DEPENDENCY_COMPATIBILITY = "dependency_compatibility"


class CheckResultStatus(StrEnum):
    """Shared pass/fail/warn outcome for preflight checks, dependency
    checks, and post-install verification checks."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class ConfigurationSection(StrEnum):
    ORGANIZATION = "organization"
    ADMINISTRATOR = "administrator"
    DATABASE = "database"
    OBJECT_STORAGE = "object_storage"
    MESSAGE_QUEUE = "message_queue"
    CACHE = "cache"
    NEO4J = "neo4j"
    AI_PROVIDER = "ai_provider"
    SMTP = "smtp"
    NOTIFICATION = "notification"
    LICENSE = "license"
    BACKUP = "backup"
    MONITORING = "monitoring"


class TlsCertificateStatus(StrEnum):
    """A certificate's own lifecycle -- see ``app.tls.engine`` for the
    classification logic this drives."""

    VALID = "valid"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SecretType(StrEnum):
    CREDENTIAL = "credential"
    CERTIFICATE = "certificate"
    KEY = "key"


class SecretStatus(StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"


class VerificationCheckType(StrEnum):
    HEALTH = "health"
    API = "api"
    AUTHENTICATION = "authentication"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    CACHE = "cache"
    NEO4J = "neo4j"
    PLUGIN = "plugin"
    PERFORMANCE = "performance"
    SMOKE_TEST = "smoke_test"


class DeploymentReportKind(StrEnum):
    INSTALLATION = "installation"
    DEPLOYMENT = "deployment"
    UPGRADE = "upgrade"
    VALIDATION = "validation"
    INFRASTRUCTURE = "infrastructure"
    ROLLBACK = "rollback"
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


class DeploymentAuditAction(StrEnum):
    """What was done, for the immutable deployment audit trail."""

    INSTALLATION = "installation"
    DEPLOYMENT = "deployment"
    CONFIGURATION_CHANGE = "configuration_change"
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"
    ADMINISTRATIVE = "administrative"


class InventoryNodeStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


__all__ = [
    "CheckResultStatus",
    "ConfigurationSection",
    "DeploymentAuditAction",
    "DeploymentEngine",
    "DeploymentJobStatus",
    "DeploymentJobType",
    "DeploymentReportKind",
    "DeploymentStrategy",
    "DeploymentTargetType",
    "InstallationMode",
    "InstallationSessionStatus",
    "InventoryNodeStatus",
    "PreflightCheckType",
    "ReportFormat",
    "ReportStatus",
    "SecretStatus",
    "SecretType",
    "TlsCertificateStatus",
    "VerificationCheckType",
]
