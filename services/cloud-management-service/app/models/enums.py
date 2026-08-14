"""Enumerations for the cloud management service.

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


class CloudProviderType(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    OCI = "oci"
    OPENSTACK = "openstack"
    VMWARE = "vmware"
    ALIBABA = "alibaba"
    IBM = "ibm"
    DIGITALOCEAN = "digitalocean"
    PRIVATE = "private"
    CUSTOM = "custom"


class CloudResourceType(StrEnum):
    VIRTUAL_MACHINE = "virtual_machine"
    CONTAINER = "container"
    MANAGED_KUBERNETES = "managed_kubernetes"
    FUNCTION = "function"
    STORAGE_BUCKET = "storage_bucket"
    BLOCK_STORAGE = "block_storage"
    FILE_STORAGE = "file_storage"
    VIRTUAL_NETWORK = "virtual_network"
    LOAD_BALANCER = "load_balancer"
    FIREWALL = "firewall"
    DNS = "dns"
    VPN = "vpn"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    SECRET = "secret"
    IDENTITY = "identity"
    AI_SERVICE = "ai_service"
    CUSTOM = "custom"


class CloudResourceLifecycleState(StrEnum):
    """A resource's position in its own lifecycle -- see
    ``app.resources.engine`` for the transition table this drives."""

    DISCOVERED = "discovered"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    UPDATING = "updating"
    SCALING = "scaling"
    SUSPENDED = "suspended"
    STOPPED = "stopped"
    DELETING = "deleting"
    DELETED = "deleted"
    ARCHIVED = "archived"
    IMPORTED = "imported"
    FAILED = "failed"


class AccountHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CloudPolicyType(StrEnum):
    TAG = "tag"
    NAMING = "naming"
    QUOTA = "quota"
    BUDGET = "budget"
    SECURITY = "security"
    APPROVAL = "approval"
    RESOURCE_RESTRICTION = "resource_restriction"


class CloudPolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class CloudComplianceFramework(StrEnum):
    CIS = "cis"
    NIST = "nist"
    ISO27001 = "iso27001"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    IEC62443 = "iec62443"
    O_PAS = "o_pas"


class CloudComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"


class DriftSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftStatus(StrEnum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IaCTool(StrEnum):
    TERRAFORM = "terraform"
    OPENTOFU = "opentofu"
    PULUMI = "pulumi"
    CLOUDFORMATION_IMPORT = "cloudformation_import"
    ARM_IMPORT = "arm_import"


class IaCDeploymentStatus(StrEnum):
    PLANNED = "planned"
    APPLYING = "applying"
    APPLIED = "applied"
    FAILED = "failed"
    DRIFTED = "drifted"
    DESTROYED = "destroyed"


class CatalogItemStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class BudgetPeriod(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ReportKind(StrEnum):
    CLOUD_INVENTORY = "cloud_inventory"
    COST = "cost"
    BUDGET = "budget"
    COMPLIANCE = "compliance"
    OPTIMIZATION = "optimization"
    CAPACITY = "capacity"
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
    """What was done, for the immutable cloud fleet audit trail."""

    ACCOUNT_REGISTERED = "account_registered"
    RESOURCE_PROVISIONED = "resource_provisioned"
    POLICY_CHANGED = "policy_changed"
    COST_CHANGED = "cost_changed"
    IAC_DEPLOYED = "iac_deployed"
    COMPLIANCE_CHANGED = "compliance_changed"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AccountHealthStatus",
    "AuditAction",
    "BudgetPeriod",
    "CatalogItemStatus",
    "CloudComplianceFramework",
    "CloudComplianceStatus",
    "CloudPolicyStatus",
    "CloudPolicyType",
    "CloudProviderType",
    "CloudResourceLifecycleState",
    "CloudResourceType",
    "DriftSeverity",
    "DriftStatus",
    "IaCDeploymentStatus",
    "IaCTool",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
]
