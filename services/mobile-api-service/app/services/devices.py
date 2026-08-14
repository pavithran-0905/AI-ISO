"""Device registration, trust transitions, and revocation.

Publishes ``MobileDeviceRegistered`` on every new device, and calls
Device Revoked directly (there is no domain event a revocation would
otherwise fan out from).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.devices.engine import TransitionResult, validate_transition
from app.events.domain_events import MobileDeviceRegisteredEvent
from app.models.devices import MobileDevice
from app.models.enums import DeviceTrustStatus, MobileAuditAction, MobilePlatform
from app.repositories.devices import MobileDeviceRepository
from app.services.audit import AuditService
from app.services.notifications import MobileNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "mobile-api-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class DeviceService:
    def __init__(
        self,
        repo: MobileDeviceRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
        notifier: MobileNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit
        self._notifier = notifier

    async def find_or_register(
        self,
        organization_id: UUID,
        *,
        device_identifier: str,
        platform: MobilePlatform,
        device_model: str | None,
        os_version: str | None,
        app_version_label: str | None,
        now: datetime,
        actor_id: str | None = None,
        is_jailbroken: bool = False,
        is_rooted: bool = False,
    ) -> tuple[MobileDevice, bool]:
        """Return the existing device, or register a new one, returning
        ``(device, was_created)``.

        Integrity flags are refreshed on every call, existing or new --
        a device's own jailbreak/root status is reported fresh on every
        registration and login, not fixed at first sight.
        """
        existing = await self._repo.find_by_identifier(
            organization_id, device_identifier=device_identifier
        )
        if existing is not None:
            existing.last_seen_at = now
            existing.os_version = os_version or existing.os_version
            existing.app_version_label = app_version_label or existing.app_version_label
            existing.is_jailbroken = is_jailbroken
            existing.is_rooted = is_rooted
            await self._repo.update(existing)
            return existing, False

        device = await self._repo.create(
            MobileDevice(
                organization_id=organization_id,
                device_identifier=device_identifier,
                platform=platform,
                device_model=device_model,
                os_version=os_version,
                app_version_label=app_version_label,
                last_seen_at=now,
                is_jailbroken=is_jailbroken,
                is_rooted=is_rooted,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=organization_id,
                action=MobileAuditAction.DEVICE_REGISTRATION,
                entity_type="mobile_device",
                entity_id=device.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Device {device_identifier!r} registered ({platform.value}).",
            )
        await self._publish(
            MobileDeviceRegisteredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "device_id": str(device.id),
                    "platform": platform.value,
                    "trust_status": (
                        device.trust_status.value
                        if isinstance(device.trust_status, DeviceTrustStatus)
                        else device.trust_status
                    ),
                },
            )
        )
        return device, True

    async def transition(
        self,
        device: MobileDevice,
        *,
        target: DeviceTrustStatus,
        now: datetime,
        actor_id: str | None = None,
    ) -> MobileDevice:
        """Move *device* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(device.trust_status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        device.trust_status = target
        if target == DeviceTrustStatus.APPROVED:
            device.approved_at = now
        elif target == DeviceTrustStatus.REVOKED:
            device.revoked_at = now
        await self._repo.update(device)

        if self._audit is not None:
            await self._audit.record(
                organization_id=device.organization_id,
                action=MobileAuditAction.ADMINISTRATIVE,
                entity_type="mobile_device",
                entity_id=device.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Device {device.device_identifier!r} moved to {target.value}.",
            )
        if target == DeviceTrustStatus.REVOKED and self._notifier is not None:
            await self._notifier.notify_device_revoked(device_identifier=device.device_identifier)
        return device


__all__ = ["DeviceService", "TransitionRefusedError"]
