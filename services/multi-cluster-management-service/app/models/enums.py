"""Enumerations for the multi-cluster management service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every other
AI-IOS service's convention), and comparable with ``==`` against a value
freshly loaded from the database, which comes back as a plain ``str``
rather than the enum instance itself.
"""

from __future__ import annotations

from enum import StrEnum


class ClusterType(StrEnum):
    """Every Kubernetes distribution/managed offering this service can
    register. ``CUSTOM_CNCF`` is the deliberate escape hatch for a
    conformant distribution not named here -- refusing to register an
    otherwise-valid CNCF cluster because its distribution isn't on a
    fixed list would defeat the point of a *multi*-cluster platform."""

    KUBERNETES = "kubernetes"
    OPENSHIFT = "openshift"
    K3S = "k3s"
    RKE2 = "rke2"
    MICROK8S = "microk8s"
    AMAZON_EKS = "amazon_eks"
    AZURE_AKS = "azure_aks"
    GOOGLE_GKE = "google_gke"
    VMWARE_TANZU = "vmware_tanzu"
    ORACLE_OKE = "oracle_oke"
    EDGE_KUBERNETES = "edge_kubernetes"
    CUSTOM_CNCF = "custom_cncf"


class ClusterLifecycleState(StrEnum):
    """A cluster's position in its own lifecycle -- see
    ``app.lifecycle.engine`` for the transition table this drives."""

    DISCOVERED = "discovered"
    REGISTERED = "registered"
    VALIDATING = "validating"
    VALIDATED = "validated"
    PROVISIONING = "provisioning"
    PROVISIONED = "provisioned"
    CONFIGURING = "configuring"
    ACTIVE = "active"
    UPGRADING = "upgrading"
    SCALING = "scaling"
    MAINTENANCE = "maintenance"
    SUSPENDED = "suspended"
    DECOMMISSIONING = "decommissioning"
    DECOMMISSIONED = "decommissioned"
    ARCHIVED = "archived"
    FAILED = "failed"


class RegistrationMethod(StrEnum):
    """How a cluster proved it is what it claims to be."""

    KUBECONFIG = "kubeconfig"
    SERVICE_ACCOUNT = "service_account"
    OIDC = "oidc"
    CERTIFICATE = "certificate"
    API_TOKEN = "api_token"
    AGENT_BASED = "agent_based"
    BOOTSTRAP_TOKEN = "bootstrap_token"
    AUTOMATIC_DISCOVERY = "automatic_discovery"


class ClusterHealthStatus(StrEnum):
    """Overall cluster health, rolled up from every component check."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ComponentHealthStatus(StrEnum):
    """One component's (API server, etcd, control plane, worker, pod)
    own health reading, before it is rolled up into
    :class:`ClusterHealthStatus`."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ClusterComponent(StrEnum):
    API_SERVER = "api_server"
    ETCD = "etcd"
    CONTROL_PLANE = "control_plane"
    WORKER_NODES = "worker_nodes"
    POD_HEALTH = "pod_health"


class ComplianceFramework(StrEnum):
    CIS_KUBERNETES = "cis_kubernetes"
    NSA_KUBERNETES = "nsa_kubernetes"
    PCI_DSS = "pci_dss"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    NIST = "nist"
    IEC62443 = "iec62443"
    O_PAS = "o_pas"


class ClusterComplianceStatus(StrEnum):
    """A cluster's standing against one framework.

    ``NOT_ASSESSED`` is a distinct, honest answer for a cluster never
    scanned against a given framework -- never assumed ``COMPLIANT`` for
    lack of a contrary finding.
    """

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_ASSESSED = "not_assessed"


class PolicyType(StrEnum):
    SECURITY = "security"
    ADMISSION = "admission"
    RESOURCE_QUOTA = "resource_quota"
    NETWORK = "network"
    RBAC = "rbac"
    OPA_GATEKEEPER = "opa_gatekeeper"
    KYVERNO = "kyverno"


class PolicyPropagationStatus(StrEnum):
    """Whether one policy has actually reached one cluster.

    ``DRIFTED`` names a policy that was applied but whose live state on
    the cluster no longer matches what was propagated -- distinct from
    ``FAILED`` (propagation itself never succeeded), because the
    remediation for each is different.
    """

    PENDING = "pending"
    PROPAGATING = "propagating"
    APPLIED = "applied"
    FAILED = "failed"
    DRIFTED = "drifted"


class UpgradeStrategy(StrEnum):
    ROLLING = "rolling"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"


class UpgradeStatus(StrEnum):
    PLANNED = "planned"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class GitOpsTool(StrEnum):
    ARGOCD = "argocd"
    FLUXCD = "fluxcd"


class SyncStatus(StrEnum):
    """A GitOps application's sync state -- see
    ``app.gitops.engine.classify_sync`` for how a desired/live state hash
    pair becomes one of these."""

    IN_SYNC = "in_sync"
    OUT_OF_SYNC = "out_of_sync"
    SYNCING = "syncing"
    UNKNOWN = "unknown"


class ServiceMeshType(StrEnum):
    NONE = "none"
    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL_CONNECT = "consul_connect"
    OPENSHIFT_SERVICE_MESH = "openshift_service_mesh"


class DeploymentStrategy(StrEnum):
    ROLLING_UPDATE = "rolling_update"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"


class WorkloadPlacementStatus(StrEnum):
    PENDING = "pending"
    PLACED = "placed"
    FAILED = "failed"
    REBALANCING = "rebalancing"


class CapacityResourceKind(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    GPU = "gpu"


class ReportKind(StrEnum):
    FLEET = "fleet"
    CAPACITY = "capacity"
    COMPLIANCE = "compliance"
    UPGRADE = "upgrade"
    HEALTH = "health"
    INVENTORY = "inventory"
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
    """What was done, for the immutable cluster fleet audit trail."""

    CLUSTER_REGISTERED = "cluster_registered"
    CREDENTIAL_CHANGED = "credential_changed"
    POLICY_UPDATED = "policy_updated"
    UPGRADE_EXECUTED = "upgrade_executed"
    COMPLIANCE_CHANGED = "compliance_changed"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AuditAction",
    "CapacityResourceKind",
    "ClusterComplianceStatus",
    "ClusterComponent",
    "ClusterHealthStatus",
    "ClusterLifecycleState",
    "ClusterType",
    "ComplianceFramework",
    "ComponentHealthStatus",
    "DeploymentStrategy",
    "GitOpsTool",
    "PolicyPropagationStatus",
    "PolicyType",
    "RegistrationMethod",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "ServiceMeshType",
    "SyncStatus",
    "UpgradeStatus",
    "UpgradeStrategy",
    "WorkloadPlacementStatus",
]
