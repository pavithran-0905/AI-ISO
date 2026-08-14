"""Cloud resource discovery, provisioning, and lifecycle transitions.

Wires ``app.resources.engine``'s pure transition table onto the
repository that persists a resource's ``lifecycle_state``, publishing
the lifecycle-boundary events docs/068 names.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import (
    CloudResourceDeletedEvent,
    CloudResourceDiscoveredEvent,
    CloudResourceProvisionedEvent,
    CloudResourceUpdatedEvent,
)
from app.models.enums import AuditAction, CloudResourceLifecycleState, CloudResourceType
from app.models.resources import CloudResource
from app.repositories.resources import CloudResourceRepository
from app.resources.engine import TransitionResult, validate_transition
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "cloud-management-service"

_PROVISIONED_SOURCES = frozenset(
    {CloudResourceLifecycleState.PROVISIONING, CloudResourceLifecycleState.IMPORTED}
)


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    """Raised when a requested lifecycle transition is not allowed."""

    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class CloudResourceService:
    """Discovers resources and drives their lifecycle transitions."""

    def __init__(
        self,
        repo: CloudResourceRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def discover(
        self,
        organization_id: UUID,
        *,
        account_id: UUID,
        resource_type: CloudResourceType,
        external_id: str,
        name: str,
        cloud_project_id: UUID | None = None,
        region_id: UUID | None = None,
        tags: dict[str, str] | None = None,
        now: datetime,
    ) -> CloudResource:
        resource = await self._repo.create(
            CloudResource(
                organization_id=organization_id,
                account_id=account_id,
                cloud_project_id=cloud_project_id,
                region_id=region_id,
                resource_type=resource_type,
                external_id=external_id,
                name=name,
                lifecycle_state=CloudResourceLifecycleState.DISCOVERED,
                tags=tags or {},
                discovered_at=now,
                last_synced_at=now,
            )
        )
        await self._publish(
            CloudResourceDiscoveredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "resource_id": str(resource.id),
                    "account_id": str(account_id),
                    "resource_type": str(resource_type),
                },
            )
        )
        return resource

    async def transition_lifecycle(
        self,
        resource: CloudResource,
        *,
        target: CloudResourceLifecycleState,
        actor_id: str | None,
        now: datetime,
    ) -> CloudResource:
        """Move *resource* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed.

        Publishes ``CloudResourceProvisioned`` on entering ``ACTIVE``
        from ``PROVISIONING``/``IMPORTED``, ``CloudResourceDeleted`` on
        entering ``DELETED``, and ``CloudResourceUpdated`` for every
        other transition -- the boundaries docs/068 names as distinct
        events, versus every other transition, which is recorded only
        on the resource's own timeline.
        """
        result = validate_transition(resource.lifecycle_state, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        # Coerced through the enum constructor: ``resource.lifecycle_state``
        # may have been read from a freshly materialized row (plain ``str``,
        # not the enum instance), and ``.value`` access below would fail on
        # a plain string.
        previous = CloudResourceLifecycleState(resource.lifecycle_state)
        resource.lifecycle_state = target
        if target == CloudResourceLifecycleState.ACTIVE:
            resource.provisioned_at = now
        await self._repo.update(resource)

        if self._audit is not None:
            await self._audit.record(
                resource.organization_id,
                action=AuditAction.RESOURCE_PROVISIONED,
                entity_type="cloud_resource",
                entity_id=resource.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Resource {resource.id!s} moved {previous.value} -> {target.value}.",
            )

        if target == CloudResourceLifecycleState.ACTIVE and previous in _PROVISIONED_SOURCES:
            await self._publish(
                CloudResourceProvisionedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=resource.organization_id,
                    payload={
                        "resource_id": str(resource.id),
                        "account_id": str(resource.account_id),
                        "lifecycle_state": str(target),
                    },
                )
            )
        elif target == CloudResourceLifecycleState.DELETED:
            await self._publish(
                CloudResourceDeletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=resource.organization_id,
                    payload={
                        "resource_id": str(resource.id),
                        "account_id": str(resource.account_id),
                    },
                )
            )
        else:
            await self._publish(
                CloudResourceUpdatedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=resource.organization_id,
                    payload={"resource_id": str(resource.id), "lifecycle_state": str(target)},
                )
            )
        return resource

    async def mark_synced(self, resource: CloudResource, *, now: datetime) -> CloudResource:
        resource.last_synced_at = now
        return await self._repo.update(resource)


__all__ = ["CloudResourceService", "TransitionRefusedError"]
