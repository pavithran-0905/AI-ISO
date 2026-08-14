"""Fleet management: edge clusters, gateways, and device registration
and lifecycle.

Wires ``app.registration.engine``'s pure credential validation onto
device enrollment, and ``app.devices.engine``'s pure transition table
onto the repository that persists a device's ``lifecycle_state``,
publishing the lifecycle-boundary events docs/067 names.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.devices.engine import TransitionResult, validate_transition
from app.events.domain_events import (
    DeviceOfflineEvent,
    DeviceOnlineEvent,
    EdgeDeviceRegisteredEvent,
)
from app.models.devices import EdgeCluster, EdgeDevice, EdgeGateway
from app.models.enums import AuditAction, DeviceLifecycleState, EdgeDeviceType
from app.registration.engine import CredentialValidation, validate_credential
from app.repositories.devices import (
    EdgeClusterRepository,
    EdgeDeviceRepository,
    EdgeGatewayRepository,
)
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "edge-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    """Raised when a requested lifecycle transition is not allowed."""

    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class CredentialRefusedError(Exception):
    """Raised when a device's enrollment credential is not usable."""

    def __init__(self, validation: CredentialValidation) -> None:
        super().__init__(validation.detail)
        self.validation = validation


class EdgeClusterService:
    def __init__(self, repo: EdgeClusterRepository) -> None:
        self._repo = repo

    async def create_cluster(
        self, organization_id: UUID, *, site_id: UUID, name: str, description: str | None
    ) -> EdgeCluster:
        return await self._repo.create(
            EdgeCluster(
                organization_id=organization_id, site_id=site_id, name=name, description=description
            )
        )


class EdgeGatewayService:
    def __init__(self, repo: EdgeGatewayRepository) -> None:
        self._repo = repo

    async def register_gateway(
        self,
        organization_id: UUID,
        *,
        site_id: UUID,
        location_id: UUID | None,
        name: str,
        ip_address: str | None,
    ) -> EdgeGateway:
        return await self._repo.create(
            EdgeGateway(
                organization_id=organization_id,
                site_id=site_id,
                location_id=location_id,
                name=name,
                lifecycle_state=DeviceLifecycleState.DISCOVERED,
                ip_address=ip_address,
            )
        )


class EdgeDeviceService:
    """Registers devices and drives their lifecycle transitions."""

    def __init__(
        self,
        repo: EdgeDeviceRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def register_device(
        self,
        organization_id: UUID,
        *,
        site_id: UUID,
        name: str,
        device_type: EdgeDeviceType,
        credential_ref: str,
        credential_expires_at: datetime | None,
        gateway_id: UUID | None = None,
        location_id: UUID | None = None,
        serial_number: str | None = None,
        actor_id: str | None,
        now: datetime,
    ) -> EdgeDevice:
        """Enroll a device, refusing an unusable credential.

        Raises:
            CredentialRefusedError: If *credential_ref* is empty or
                already expired.
        """
        validation = validate_credential(credential_ref, expires_at=credential_expires_at, now=now)
        if not validation.is_valid:
            raise CredentialRefusedError(validation)

        device = await self._repo.create(
            EdgeDevice(
                organization_id=organization_id,
                site_id=site_id,
                gateway_id=gateway_id,
                location_id=location_id,
                name=name,
                device_type=device_type,
                lifecycle_state=DeviceLifecycleState.REGISTERED,
                serial_number=serial_number,
                registered_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.DEVICE_REGISTERED,
                entity_type="edge_device",
                entity_id=device.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Registered device {name!r} ({device_type.value}).",
            )
        await self._publish(
            EdgeDeviceRegisteredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "device_id": str(device.id),
                    "site_id": str(site_id),
                    "device_type": str(device_type),
                },
            )
        )
        return device

    async def transition_lifecycle(
        self, device: EdgeDevice, *, target: DeviceLifecycleState, now: datetime
    ) -> EdgeDevice:
        """Move *device* to *target*, raising :class:`TransitionRefusedError`
        if the transition is not allowed."""
        result = validate_transition(device.lifecycle_state, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        device.lifecycle_state = target
        return await self._repo.update(device)

    async def mark_online(self, device: EdgeDevice, *, now: datetime) -> EdgeDevice:
        was_online = device.is_online
        device.is_online = True
        device.last_seen_at = now
        await self._repo.update(device)
        if not was_online:
            await self._publish(
                DeviceOnlineEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=device.organization_id,
                    payload={"device_id": str(device.id), "last_seen_at": now.isoformat()},
                )
            )
        return device

    async def mark_offline(self, device: EdgeDevice, *, now: datetime) -> EdgeDevice:
        was_online = device.is_online
        device.is_online = False
        await self._repo.update(device)
        if was_online:
            last_seen = device.last_seen_at.isoformat() if device.last_seen_at else None
            await self._publish(
                DeviceOfflineEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=device.organization_id,
                    payload={"device_id": str(device.id), "last_seen_at": last_seen},
                )
            )
        return device

    async def cordon(self, device: EdgeDevice) -> EdgeDevice:
        """Stop new workloads/updates from being scheduled onto *device*
        without otherwise disturbing it."""
        device.is_schedulable = False
        return await self._repo.update(device)

    async def uncordon(self, device: EdgeDevice) -> EdgeDevice:
        device.is_schedulable = True
        return await self._repo.update(device)


__all__ = [
    "CredentialRefusedError",
    "EdgeClusterService",
    "EdgeDeviceService",
    "EdgeGatewayService",
    "TransitionRefusedError",
]
