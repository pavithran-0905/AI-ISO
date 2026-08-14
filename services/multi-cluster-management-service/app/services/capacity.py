"""Cluster capacity recording and classification.

Wires ``app.capacity.engine``'s pure utilization/severity classification
onto the repository that persists capacity readings.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.capacity.engine import UtilizationAssessment, classify_utilization, compute_utilization
from app.models.enums import CapacityResourceKind
from app.models.operations import ClusterCapacity
from app.repositories.operations import ClusterCapacityRepository


class CapacityService:
    def __init__(self, repo: ClusterCapacityRepository) -> None:
        self._repo = repo

    async def record_reading(
        self,
        organization_id: UUID,
        *,
        cluster_id: UUID,
        resource_kind: CapacityResourceKind,
        total: float,
        used: float,
        measured_at: datetime,
    ) -> ClusterCapacity:
        return await self._repo.create(
            ClusterCapacity(
                organization_id=organization_id,
                cluster_id=cluster_id,
                resource_kind=resource_kind,
                total=total,
                used=used,
                measured_at=measured_at,
            )
        )

    def assess(
        self, reading: ClusterCapacity, *, warning_threshold: float, critical_threshold: float
    ) -> UtilizationAssessment:
        utilization = compute_utilization(reading.total, reading.used)
        return classify_utilization(
            utilization, warning_threshold=warning_threshold, critical_threshold=critical_threshold
        )


__all__ = ["CapacityService"]
