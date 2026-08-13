"""The vocabulary this service reasons in (docs/065).

Every enum here is a decision about what distinctions are worth keeping.
``BackupJobStatus.VERIFIED`` is separate from ``COMPLETED`` because a
backup that finished writing and a backup that has been proven readable
are different claims; collapsing them is how a corrupted backup is
discovered for the first time during the disaster it was meant to
prevent.
"""

from __future__ import annotations

from enum import StrEnum

# ---- targets and backup shape --------------------------------------------------------


class BackupTargetKind(StrEnum):
    """What is being backed up, per the spec's BACKUP TARGETS list."""

    POSTGRESQL = "postgresql"
    NEO4J = "neo4j"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    MINIO = "minio"
    CONFIGURATION_FILES = "configuration_files"
    SECRETS_METADATA = "secrets_metadata"
    WORKFLOW_DEFINITIONS = "workflow_definitions"
    AUTOMATION_PLAYBOOKS = "automation_playbooks"
    PROMPT_LIBRARY = "prompt_library"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    RAG_INDEX_METADATA = "rag_index_metadata"
    DOCUMENT_METADATA = "document_metadata"
    PLUGIN_METADATA = "plugin_metadata"
    CONNECTOR_CONFIGURATIONS = "connector_configurations"
    KUBERNETES_RESOURCES = "kubernetes_resources"
    DOCKER_VOLUMES = "docker_volumes"
    PERSISTENT_VOLUMES = "persistent_volumes"
    CUSTOM_RESOURCES = "custom_resources"


class BackupType(StrEnum):
    """How a backup relates to the ones before it.

    ``INCREMENTAL`` and ``DIFFERENTIAL`` are not interchangeable: an
    incremental restore chain needs every incremental since the last
    full, while a differential restore needs only the full plus the
    latest differential. Confusing the two during restore planning
    produces a chain that is missing links or a chain with links it does
    not need -- both are a wrong restore, not a slow one.
    """

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    CONTINUOUS = "continuous"
    POINT_IN_TIME = "point_in_time"
    APPLICATION_CONSISTENT = "application_consistent"
    CRASH_CONSISTENT = "crash_consistent"


class ConsistencyLevel(StrEnum):
    """Whether a backup captured a coordinated, application-aware state.

    A crash-consistent backup is what a hard power-off would have left
    behind -- valid for a filesystem, not guaranteed valid for a database
    with in-flight transactions. Restoring one without knowing which kind
    it is invites trusting data a WAL replay was actually needed to make
    consistent.
    """

    APPLICATION_CONSISTENT = "application_consistent"
    CRASH_CONSISTENT = "crash_consistent"
    UNKNOWN = "unknown"


class BackupJobStatus(StrEnum):
    """Where one backup run stands.

    ``VERIFIED`` is reached only via a separate verification pass, never
    implied by ``COMPLETED``: a backup that finished writing every byte
    can still be unreadable, and the two claims need different evidence.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class ScheduleFrequency(StrEnum):
    """How often a backup schedule fires."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM_CRON = "custom_cron"


# ---- snapshots ------------------------------------------------------------------------


class SnapshotKind(StrEnum):
    """What layer a snapshot was taken at, per the spec's SNAPSHOTS list."""

    FILESYSTEM = "filesystem"
    VOLUME = "volume"
    DATABASE = "database"
    KUBERNETES_VOLUME_SNAPSHOT = "kubernetes_volume_snapshot"
    CLOUD = "cloud"


class SnapshotStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    AVAILABLE = "available"
    VALIDATED = "validated"
    EXPIRED = "expired"
    FAILED = "failed"
    DELETED = "deleted"


# ---- restore --------------------------------------------------------------------------


class RestoreKind(StrEnum):
    """What scope a restore covers, per the spec's RESTORE list."""

    FULL = "full"
    PARTIAL = "partial"
    OBJECT_LEVEL = "object_level"
    TABLE = "table"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    WORKFLOW = "workflow"
    PLUGIN = "plugin"
    CROSS_VERSION = "cross_version"
    POINT_IN_TIME = "point_in_time"
    SELECTIVE = "selective"


class RestoreJobStatus(StrEnum):
    PENDING = "pending"
    PREVIEWING = "previewing"
    RUNNING = "running"
    COMPLETED = "completed"
    VALIDATED = "validated"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RestorePointKind(StrEnum):
    """How a restore point's instant was established."""

    SNAPSHOT = "snapshot"
    WAL_POSITION = "wal_position"
    TRANSACTION_MARKER = "transaction_marker"
    BACKUP_COMPLETION = "backup_completion"


# ---- replication ------------------------------------------------------------------------


class ReplicationMode(StrEnum):
    """Synchronous replication acknowledges the replica before the
    write returns; asynchronous does not. The choice trades write
    latency against how much data a primary failure can lose, and no
    default is safe for every target -- see docs/065's own REPLICATION
    section."""

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"


class ReplicationScope(StrEnum):
    LOCAL = "local"
    CROSS_REGION = "cross_region"
    CROSS_CLUSTER = "cross_cluster"


class ReplicationStatus(StrEnum):
    PENDING = "pending"
    SYNCING = "syncing"
    IN_SYNC = "in_sync"
    LAGGING = "lagging"
    STALLED = "stalled"
    FAILED = "failed"
    STOPPED = "stopped"


# ---- disaster recovery ------------------------------------------------------------------


class DrPlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class RecoveryPriority(StrEnum):
    """How urgently a recovery group must come back, per the spec's
    RECOVERY PRIORITIES. Ordinal, not numeric: a priority compiled into
    a number invites averaging groups together, which a sequencing
    decision must never do."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DrTestStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class DrTestKind(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    SIMULATION = "simulation"


# ---- failover ---------------------------------------------------------------------------


class FailoverKind(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    FAILBACK = "failback"


class FailoverStatus(StrEnum):
    INITIATED = "initiated"
    HEALTH_CHECKING = "health_checking"
    SWITCHING = "switching"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# ---- runbooks -----------------------------------------------------------------------------


class RunbookStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# ---- encryption / immutability ------------------------------------------------------------


class ImmutabilityState(StrEnum):
    """Whether an archive can currently be deleted.

    ``LEGAL_HOLD`` outranks an expired retention lock deliberately: a
    lock with a stated end date is a policy, a legal hold is an order,
    and the second must never quietly lapse because the first's timer
    ran out.
    """

    NONE = "none"
    RETENTION_LOCKED = "retention_locked"
    LEGAL_HOLD = "legal_hold"


# ---- verification -----------------------------------------------------------------------------


class VerificationKind(StrEnum):
    CHECKSUM = "checksum"
    INTEGRITY = "integrity"
    SAMPLE_RESTORE = "sample_restore"
    PERIODIC = "periodic"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---- retention ------------------------------------------------------------------------------


class RetentionTier(StrEnum):
    """Where an archive currently lives, per the spec's tiered storage
    requirement. A tier is a placement decision, never a deletion one --
    see :mod:`app.retention.engine`."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"


# ---- compliance / reporting -------------------------------------------------------------------


class ComplianceStatus(StrEnum):
    """Whether a recovery met the objective it was measured against.

    ``NOT_MEASURED`` is a distinct, honest answer for a DR plan that has
    never actually been tested -- reporting ``MET`` for an unmeasured
    plan would be exactly the ransomware-day surprise this service
    exists to prevent.
    """

    MET = "met"
    VIOLATED = "violated"
    NOT_MEASURED = "not_measured"


class ReportKind(StrEnum):
    BACKUP = "backup"
    RESTORE = "restore"
    RECOVERY = "recovery"
    REPLICATION = "replication"
    COMPLIANCE = "compliance"
    STORAGE = "storage"
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
    """What was done, for the immutable trail."""

    BACKUP_CONFIGURED = "backup_configured"
    BACKUP_EXECUTED = "backup_executed"
    RESTORE_REQUESTED = "restore_requested"
    RESTORE_EXECUTED = "restore_executed"
    RECOVERY_EXECUTED = "recovery_executed"
    RETENTION_CHANGED = "retention_changed"
    DR_PLAN_CHANGED = "dr_plan_changed"
    FAILOVER_EXECUTED = "failover_executed"
    RUNBOOK_APPROVED = "runbook_approved"
    LEGAL_HOLD_APPLIED = "legal_hold_applied"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AuditAction",
    "BackupJobStatus",
    "BackupTargetKind",
    "BackupType",
    "ComplianceStatus",
    "ConsistencyLevel",
    "DrPlanStatus",
    "DrTestKind",
    "DrTestStatus",
    "FailoverKind",
    "FailoverStatus",
    "ImmutabilityState",
    "RecoveryPriority",
    "ReplicationMode",
    "ReplicationScope",
    "ReplicationStatus",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "RestoreJobStatus",
    "RestoreKind",
    "RestorePointKind",
    "RetentionTier",
    "RunbookStatus",
    "ScheduleFrequency",
    "SnapshotKind",
    "SnapshotStatus",
    "VerificationKind",
    "VerificationStatus",
]
