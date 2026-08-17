"""Every enum this service's models and engines use (docs/079)."""

from __future__ import annotations

from enum import StrEnum


class HardeningTargetType(StrEnum):
    """What kind of system a hardening profile targets."""

    OS = "os"
    CONTAINER = "container"
    KUBERNETES = "kubernetes"
    API = "api"
    DATABASE = "database"
    NETWORK = "network"
    TLS = "tls"
    IDENTITY = "identity"
    SECRETS = "secrets"
    LOGGING = "logging"


class CisBenchmark(StrEnum):
    """Which CIS (or custom) benchmark a hardening profile is scored
    against."""

    LINUX_CIS = "linux_cis"
    DOCKER_CIS = "docker_cis"
    KUBERNETES_CIS = "kubernetes_cis"
    POSTGRESQL_CIS = "postgresql_cis"
    REDIS_CIS = "redis_cis"
    RABBITMQ_CIS = "rabbitmq_cis"
    NGINX_CIS = "nginx_cis"
    CUSTOM = "custom"


class HardeningRunStatus(StrEnum):
    """The shared job lifecycle every hardening run drives through --
    see ``app.hardening.engine``."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CheckResultStatus(StrEnum):
    """A generic pass/warn/fail outcome, shared across hardening
    results, operational readiness checks, and disaster recovery
    checks."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class FindingSeverity(StrEnum):
    """How severe a security finding, vulnerability, or runtime
    protection event is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    """Where a security finding stands in its own remediation
    lifecycle."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class VulnerabilityScanType(StrEnum):
    """What kind of scan detected a vulnerability."""

    DEPENDENCY = "dependency"
    CONTAINER = "container"
    OS_PACKAGE = "os_package"
    SECRETS = "secrets"
    LICENSE = "license"


class RemediationStatus(StrEnum):
    """Where a detected vulnerability stands in its own remediation
    lifecycle."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REMEDIATED = "remediated"
    ACCEPTED_RISK = "accepted_risk"


class RuntimeProtectionEventType(StrEnum):
    """What kind of runtime protection event was recorded."""

    THREAT_DETECTION = "threat_detection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    FILE_INTEGRITY = "file_integrity"
    ANOMALY = "anomaly"
    POLICY_VIOLATION = "policy_violation"


class ComplianceFramework(StrEnum):
    """Which compliance framework a compliance result is evaluated
    against."""

    ISO27001 = "iso27001"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    NIST = "nist"
    IEC62443 = "iec62443"
    O_PAS = "o_pas"
    INTERNAL = "internal"


class CertificationStatus(StrEnum):
    """Where a production certification stands in its own lifecycle."""

    PENDING = "pending"
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OperationalReadinessCheckType(StrEnum):
    """What kind of operational readiness check was performed."""

    RUNBOOK = "runbook"
    MONITORING = "monitoring"
    ALERTING = "alerting"
    LOGGING = "logging"
    TELEMETRY = "telemetry"
    SCALING = "scaling"
    CAPACITY = "capacity"
    SUPPORT = "support"
    SLA = "sla"


class DisasterRecoveryCheckType(StrEnum):
    """What kind of disaster recovery validation was performed."""

    BACKUP_VALIDATION = "backup_validation"
    RESTORE_VALIDATION = "restore_validation"
    RTO_VALIDATION = "rto_validation"
    RPO_VALIDATION = "rpo_validation"
    FAILOVER_VALIDATION = "failover_validation"
    DR_DRILL = "dr_drill"
    BUSINESS_CONTINUITY = "business_continuity"


class HardeningReportKind(StrEnum):
    """What a generated report covers."""

    HARDENING = "hardening"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    VULNERABILITY = "vulnerability"
    SBOM = "sbom"
    CERTIFICATION = "certification"
    OPERATIONAL_READINESS = "operational_readiness"
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


class HardeningAuditAction(StrEnum):
    """What was done, for the immutable hardening audit trail."""

    HARDENING_RUN = "hardening_run"
    SECURITY_CHANGE = "security_change"
    CERTIFICATION_DECISION = "certification_decision"
    COMPLIANCE_VALIDATION = "compliance_validation"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "CertificationStatus",
    "CheckResultStatus",
    "CisBenchmark",
    "ComplianceFramework",
    "DisasterRecoveryCheckType",
    "FindingSeverity",
    "FindingStatus",
    "HardeningAuditAction",
    "HardeningReportKind",
    "HardeningRunStatus",
    "HardeningTargetType",
    "OperationalReadinessCheckType",
    "RemediationStatus",
    "ReportFormat",
    "ReportStatus",
    "RuntimeProtectionEventType",
    "VulnerabilityScanType",
]
