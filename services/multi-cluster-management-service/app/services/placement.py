"""Workload placement.

Wires ``app.placement.engine``'s pure affinity evaluation onto the
repository that persists workload placement records.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import DeploymentStrategy, WorkloadPlacementStatus
from app.models.fleet import Cluster
from app.models.reporting import ClusterWorkload
from app.placement.engine import PlacementCandidate, select_placement_candidates
from app.repositories.reporting import ClusterWorkloadRepository


class PlacementService:
    def __init__(self, repo: ClusterWorkloadRepository) -> None:
        self._repo = repo

    def select_candidates(
        self,
        clusters: list[Cluster],
        *,
        required_labels: dict[str, str],
        forbidden_labels: dict[str, str],
    ) -> tuple[UUID, ...]:
        candidates = [PlacementCandidate(cluster_id=c.id, labels=c.labels) for c in clusters]
        return select_placement_candidates(
            candidates, required_labels=required_labels, forbidden_labels=forbidden_labels
        )

    async def place_workload(
        self,
        organization_id: UUID,
        *,
        name: str,
        namespace: str | None,
        cluster_id: UUID | None,
        deployment_strategy: DeploymentStrategy,
        replicas: int | None,
        affinity_rules: dict[str, object],
        now: datetime,
    ) -> ClusterWorkload:
        """Persist a workload placement.

        ``cluster_id is None`` records the workload as ``FAILED`` --
        placement was requested but no eligible cluster was found by
        :meth:`select_candidates`, and that outcome is worth keeping on
        record rather than silently dropping the request.
        """
        is_placed = cluster_id is not None
        return await self._repo.create(
            ClusterWorkload(
                organization_id=organization_id,
                cluster_id=cluster_id,
                name=name,
                namespace=namespace,
                deployment_strategy=deployment_strategy,
                placement_status=(
                    WorkloadPlacementStatus.PLACED if is_placed else WorkloadPlacementStatus.FAILED
                ),
                replicas=replicas,
                affinity_rules=affinity_rules,
                placed_at=now if is_placed else None,
            )
        )

    async def drain_cluster(self, cluster_id: UUID) -> int:
        """Mark every currently-placed workload on *cluster_id* for
        rebalancing elsewhere. Returns how many were marked.

        This records the *intent* to move workloads off the cluster --
        actually rescheduling them onto a different cluster is a
        follow-up placement decision this service does not make for the
        caller automatically, since the right destination depends on
        constraints (capacity, affinity) only a fresh placement
        evaluation should decide.
        """
        workloads = await self._repo.list_for_cluster(cluster_id)
        count = 0
        for workload in workloads:
            # ``==`` (StrEnum equality), never ``is``: a row freshly
            # materialized from the database -- rather than found already
            # live in the session's identity map -- carries a plain ``str``
            # for this column, not the enum instance, since the column
            # itself is declared as ``String`` with no Enum type decorator.
            if workload.placement_status == WorkloadPlacementStatus.PLACED:
                workload.placement_status = WorkloadPlacementStatus.REBALANCING
                await self._repo.update(workload)
                count += 1
        return count


__all__ = ["PlacementService"]
