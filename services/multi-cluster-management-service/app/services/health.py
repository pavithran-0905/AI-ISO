"""Cluster health recording and aggregation.

Wires ``app.health.engine``'s pure component rollup onto the repository
that persists health readings and the cluster's own denormalized
``health_status``, and publishes ``ClusterHealthChanged`` only on an
actual status transition -- never on every check, which would flood
subscribers with an event for a cluster that has been healthy for weeks.
"""

from __future__ import annotations

from datetime import datetime

from app.events.domain_events import ClusterHealthChangedEvent
from app.health.engine import ComponentReading, HealthAggregation, aggregate_health
from app.models.enums import ClusterComponent, ComponentHealthStatus
from app.models.fleet import Cluster
from app.models.operations import ClusterHealth
from app.repositories.fleet import ClusterRepository
from app.repositories.operations import ClusterHealthRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "multi-cluster-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class HealthService:
    def __init__(
        self,
        health_repo: ClusterHealthRepository,
        cluster_repo: ClusterRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._health_repo = health_repo
        self._cluster_repo = cluster_repo
        self._publish = publish

    async def record_reading(
        self,
        cluster: Cluster,
        *,
        component: ClusterComponent,
        status: ComponentHealthStatus,
        detail: str | None,
        now: datetime,
    ) -> ClusterHealth:
        return await self._health_repo.create(
            ClusterHealth(
                organization_id=cluster.organization_id,
                cluster_id=cluster.id,
                component=component,
                status=status,
                detail=detail,
                checked_at=now,
            )
        )

    async def refresh_overall_status(
        self,
        cluster: Cluster,
        *,
        degraded_threshold: int,
        unhealthy_threshold: int,
        now: datetime,
    ) -> HealthAggregation:
        """Recompute *cluster*'s overall health from its latest
        per-component readings and persist it, publishing
        ``ClusterHealthChanged`` if it actually changed."""
        rows = await self._health_repo.latest_per_component(cluster.id)
        readings = [ComponentReading(component=row.component, status=row.status) for row in rows]
        aggregation = aggregate_health(
            readings, degraded_threshold=degraded_threshold, unhealthy_threshold=unhealthy_threshold
        )

        previous_status = cluster.health_status
        cluster.health_status = aggregation.overall
        cluster.last_health_check_at = now
        await self._cluster_repo.update(cluster)

        if aggregation.overall != previous_status:
            await self._publish(
                ClusterHealthChangedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=cluster.organization_id,
                    payload={
                        "cluster_id": str(cluster.id),
                        "previous_status": str(previous_status),
                        "new_status": str(aggregation.overall),
                    },
                )
            )
        return aggregation


__all__ = ["HealthService"]
