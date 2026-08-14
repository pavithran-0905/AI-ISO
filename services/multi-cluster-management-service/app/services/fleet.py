"""Fleet management: cluster groups, regions, registration, and
lifecycle transitions.

Wires ``app.lifecycle.engine``'s pure transition table onto the
repository that persists a cluster's ``lifecycle_state``, and publishes
the lifecycle-boundary events docs/066 names.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import (
    ClusterProvisionedEvent,
    ClusterRegisteredEvent,
    ClusterRemovedEvent,
)
from app.lifecycle.engine import TransitionResult, validate_transition
from app.models.enums import AuditAction, ClusterLifecycleState, ClusterType
from app.models.fleet import Cluster, ClusterGroup, ClusterRegion
from app.repositories.fleet import (
    ClusterGroupRepository,
    ClusterRegionRepository,
    ClusterRepository,
)
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "multi-cluster-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    """Raised when a requested lifecycle transition is not allowed."""

    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class ClusterGroupService:
    def __init__(self, repo: ClusterGroupRepository) -> None:
        self._repo = repo

    async def create_group(
        self,
        organization_id: UUID,
        *,
        name: str,
        description: str | None,
        business_unit: str | None,
    ) -> ClusterGroup:
        return await self._repo.create(
            ClusterGroup(
                organization_id=organization_id,
                name=name,
                description=description,
                business_unit=business_unit,
            )
        )


class ClusterRegionService:
    def __init__(self, repo: ClusterRegionRepository) -> None:
        self._repo = repo

    async def create_region(
        self,
        organization_id: UUID,
        *,
        name: str,
        code: str,
        provider: str | None,
        availability_zones: list[str],
    ) -> ClusterRegion:
        return await self._repo.create(
            ClusterRegion(
                organization_id=organization_id,
                name=name,
                code=code,
                provider=provider,
                availability_zones=availability_zones,
            )
        )


class ClusterService:
    """Registers clusters and drives their lifecycle transitions."""

    def __init__(
        self,
        repo: ClusterRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def register_cluster(
        self,
        organization_id: UUID,
        *,
        name: str,
        cluster_type: ClusterType,
        environment: str,
        group_id: UUID | None,
        region_id: UUID | None,
        actor_id: str | None,
        now: datetime,
    ) -> Cluster:
        cluster = await self._repo.create(
            Cluster(
                organization_id=organization_id,
                name=name,
                cluster_type=cluster_type,
                lifecycle_state=ClusterLifecycleState.DISCOVERED,
                environment=environment,
                group_id=group_id,
                region_id=region_id,
                registered_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.CLUSTER_REGISTERED,
                entity_type="cluster",
                entity_id=cluster.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Registered cluster {name!r} ({cluster_type.value}).",
            )
        await self._publish(
            ClusterRegisteredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "cluster_id": str(cluster.id),
                    "name": name,
                    "cluster_type": str(cluster_type),
                },
            )
        )
        return cluster

    async def transition_lifecycle(
        self, cluster: Cluster, *, target: ClusterLifecycleState, now: datetime
    ) -> Cluster:
        """Move *cluster* to *target*, raising :class:`TransitionRefusedError`
        if the transition is not allowed.

        Publishes ``ClusterProvisioned`` on entering ``ACTIVE`` for the
        first time via ``CONFIGURING``, and ``ClusterRemoved`` on
        entering ``ARCHIVED`` -- the two lifecycle boundaries docs/066
        names as distinct events, versus every other transition, which
        is recorded only on the cluster's own timeline.
        """
        result = validate_transition(cluster.lifecycle_state, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        previous = cluster.lifecycle_state
        cluster.lifecycle_state = target
        await self._repo.update(cluster)

        # ``==``, never ``is``: ``previous`` may have been read from a
        # freshly materialized row (plain ``str``, not the enum instance),
        # so identity comparison against it is not reliable.
        if target == ClusterLifecycleState.ACTIVE and previous == ClusterLifecycleState.CONFIGURING:
            await self._publish(
                ClusterProvisionedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=cluster.organization_id,
                    payload={"cluster_id": str(cluster.id), "lifecycle_state": str(target)},
                )
            )
        elif target == ClusterLifecycleState.ARCHIVED:
            await self._publish(
                ClusterRemovedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=cluster.organization_id,
                    payload={"cluster_id": str(cluster.id), "lifecycle_state": str(target)},
                )
            )
        return cluster

    async def cordon(self, cluster: Cluster) -> Cluster:
        """Stop new workloads from being placed on *cluster* without
        otherwise disturbing it."""
        cluster.is_schedulable = False
        return await self._repo.update(cluster)

    async def uncordon(self, cluster: Cluster) -> Cluster:
        cluster.is_schedulable = True
        return await self._repo.update(cluster)


__all__ = [
    "ClusterGroupService",
    "ClusterRegionService",
    "ClusterService",
    "TransitionRefusedError",
]
