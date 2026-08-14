"""Every persisted model.

All three modules are imported here so Alembic's autogenerate sees the
whole metadata. A model that is not imported is a table the migration
will not create -- and the failure surfaces as a missing relation at
runtime, long after the migration looked like it worked.
"""

from app.models.fleet import Cluster, ClusterCredential, ClusterGroup, ClusterRegion, ClusterVersion
from app.models.operations import (
    ClusterCapacity,
    ClusterCompliance,
    ClusterHealth,
    ClusterInventory,
    ClusterPolicy,
    ClusterUpgrade,
)
from app.models.reporting import (
    ClusterAudit,
    ClusterEvent,
    ClusterReport,
    ClusterStatistic,
    ClusterWorkload,
)

__all__ = [
    "Cluster",
    "ClusterAudit",
    "ClusterCapacity",
    "ClusterCompliance",
    "ClusterCredential",
    "ClusterEvent",
    "ClusterGroup",
    "ClusterHealth",
    "ClusterInventory",
    "ClusterPolicy",
    "ClusterRegion",
    "ClusterReport",
    "ClusterStatistic",
    "ClusterUpgrade",
    "ClusterVersion",
    "ClusterWorkload",
]
