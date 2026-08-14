"""OTA update planning and execution.

Wires ``app.ota.engine``'s pure version-skew validation and rollback
decision onto the repositories that persist the firmware catalog and
update executions, publishing ``OTAStarted``/``OTACompleted``.
"""

from __future__ import annotations

from datetime import datetime

from app.events.domain_events import OTACompletedEvent, OTAStartedEvent
from app.models.devices import EdgeDevice
from app.models.enums import UpdateKind, UpdateStatus, UpdateStrategy
from app.models.operations import EdgeUpdate
from app.ota.engine import UpdatePlanValidation, should_roll_back, validate_update_plan
from app.repositories.operations import EdgeFirmwareRepository, EdgeUpdateRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "edge-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class UpdatePlanRefusedError(Exception):
    def __init__(self, validation: UpdatePlanValidation) -> None:
        super().__init__(validation.detail)
        self.validation = validation


class OTAService:
    def __init__(
        self,
        repo: EdgeUpdateRepository,
        firmware_repo: EdgeFirmwareRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        max_skew: int,
    ) -> None:
        self._repo = repo
        self._firmware_repo = firmware_repo
        self._publish = publish
        self._max_skew = max_skew

    async def plan_update(
        self,
        device: EdgeDevice,
        *,
        update_kind: UpdateKind,
        strategy: UpdateStrategy,
        to_version: str,
    ) -> EdgeUpdate:
        """Validate and persist an update plan for *device*.

        Raises:
            UpdatePlanRefusedError: If the target version is not a valid
                forward step within the configured max skew of the
                device's current catalog rank.
        """
        from_version = device.firmware_version or ""
        current_entry = await self._firmware_repo.find_by_type_and_version(
            device.device_type, from_version
        )
        target_entry = await self._firmware_repo.find_by_type_and_version(
            device.device_type, to_version
        )
        from_rank = current_entry.skew_rank if current_entry is not None else 0
        to_rank = target_entry.skew_rank if target_entry is not None else 0

        validation = validate_update_plan(from_rank, to_rank, max_skew=self._max_skew)
        if not validation.is_valid:
            raise UpdatePlanRefusedError(validation)

        return await self._repo.create(
            EdgeUpdate(
                organization_id=device.organization_id,
                device_id=device.id,
                update_kind=update_kind,
                strategy=strategy,
                from_version=from_version or "unknown",
                to_version=to_version,
                status=UpdateStatus.PLANNED,
            )
        )

    async def start_update(self, update: EdgeUpdate, *, now: datetime) -> EdgeUpdate:
        update.status = UpdateStatus.APPLYING
        update.started_at = now
        await self._repo.update(update)
        await self._publish(
            OTAStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=update.organization_id,
                payload={
                    "device_id": str(update.device_id),
                    "update_id": str(update.id),
                    "from_version": update.from_version,
                    "to_version": update.to_version,
                },
            )
        )
        return update

    async def complete_update(
        self,
        update: EdgeUpdate,
        device: EdgeDevice,
        *,
        verification_passed: bool | None,
        now: datetime,
    ) -> EdgeUpdate:
        """Finish *update*, marking it rolled back if verification
        explicitly failed, and advancing the device's firmware version
        on success."""
        update.verification_passed = verification_passed
        update.completed_at = now
        update.duration_ms = (
            (now - update.started_at).total_seconds() * 1000.0 if update.started_at else None
        )
        update.status = (
            UpdateStatus.ROLLED_BACK
            if should_roll_back(verification_passed=verification_passed)
            else UpdateStatus.COMPLETED
        )
        await self._repo.update(update)

        if update.status == UpdateStatus.COMPLETED:
            device.firmware_version = update.to_version

        await self._publish(
            OTACompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=update.organization_id,
                payload={
                    "device_id": str(update.device_id),
                    "update_id": str(update.id),
                    "status": str(update.status),
                },
            )
        )
        return update

    async def fail_update(
        self, update: EdgeUpdate, *, error_message: str, now: datetime
    ) -> EdgeUpdate:
        update.status = UpdateStatus.FAILED
        update.completed_at = now
        update.error_message = error_message
        await self._repo.update(update)
        await self._publish(
            OTACompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=update.organization_id,
                payload={
                    "device_id": str(update.device_id),
                    "update_id": str(update.id),
                    "status": str(update.status),
                },
            )
        )
        return update


__all__ = ["OTAService", "UpdatePlanRefusedError"]
