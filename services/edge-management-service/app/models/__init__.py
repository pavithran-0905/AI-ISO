"""Every persisted model.

All four modules are imported here so Alembic's autogenerate sees the
whole metadata. A model that is not imported is a table the migration
will not create -- and the failure surfaces as a missing relation at
runtime, long after the migration looked like it worked.
"""

from app.models.devices import EdgeCluster, EdgeDevice, EdgeGateway, EdgeInventory
from app.models.operations import (
    EdgeAiModel,
    EdgeApplication,
    EdgeConfiguration,
    EdgeFirmware,
    EdgeHealth,
    EdgeProtocol,
    EdgeSynchronization,
    EdgeUpdate,
)
from app.models.reporting import EdgeAudit, EdgeReport, EdgeStatistic
from app.models.sites import EdgeLocation, EdgeSite

__all__ = [
    "EdgeAiModel",
    "EdgeApplication",
    "EdgeAudit",
    "EdgeCluster",
    "EdgeConfiguration",
    "EdgeDevice",
    "EdgeFirmware",
    "EdgeGateway",
    "EdgeHealth",
    "EdgeInventory",
    "EdgeLocation",
    "EdgeProtocol",
    "EdgeReport",
    "EdgeSite",
    "EdgeStatistic",
    "EdgeSynchronization",
    "EdgeUpdate",
]
