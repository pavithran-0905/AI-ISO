"""License issuance, lifecycle transitions, and seat activation.

Wires ``app.licenses.engine``'s pure transition table and seat-limit
check onto the repositories that persist licenses and activations,
publishing ``LicenseActivated``/``LicenseRevoked``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import LicenseActivatedEvent, LicenseRevokedEvent
from app.licenses.engine import TransitionResult, has_seat_available, validate_transition
from app.models.enums import AuditAction, LicenseModel, LicenseStatus
from app.models.licenses import License, LicenseActivation
from app.repositories.licenses import LicenseActivationRepository, LicenseRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class SeatLimitReachedError(Exception):
    """Raised when a license has no seats left to activate."""

    def __init__(self, license_id: UUID) -> None:
        super().__init__(f"License {license_id!s} has no seats available for another activation.")
        self.license_id = license_id


class LicenseService:
    def __init__(
        self,
        license_repo: LicenseRepository,
        activation_repo: LicenseActivationRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._license_repo = license_repo
        self._activation_repo = activation_repo
        self._publish = publish
        self._audit = audit

    async def issue_license(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        subscription_id: UUID | None,
        license_model: LicenseModel,
        expires_at: datetime | None,
        seat_limit: int | None,
        actor_id: str | None,
        now: datetime,
    ) -> License:
        license_row = await self._license_repo.create(
            License(
                organization_id=organization_id,
                customer_id=customer_id,
                subscription_id=subscription_id,
                license_model=license_model,
                status=LicenseStatus.ISSUED,
                issued_at=now,
                expires_at=expires_at,
                seat_limit=seat_limit,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.LICENSE_CREATED,
                entity_type="license",
                entity_id=license_row.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Issued {license_model.value} license for customer {customer_id!s}.",
            )
        return license_row

    async def transition(
        self, license_row: License, *, target: LicenseStatus, actor_id: str | None, now: datetime
    ) -> License:
        """Move *license_row* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(license_row.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        license_row.status = target
        await self._license_repo.update(license_row)

        if self._audit is not None:
            await self._audit.record(
                license_row.organization_id,
                action=AuditAction.LICENSE_CREATED,
                entity_type="license",
                entity_id=license_row.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"License {license_row.id!s} moved to {target.value}.",
            )

        if target == LicenseStatus.REVOKED:
            await self._publish(
                LicenseRevokedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=license_row.organization_id,
                    payload={
                        "license_id": str(license_row.id),
                        "customer_id": str(license_row.customer_id),
                    },
                )
            )
        return license_row

    async def activate_seat(
        self, license_row: License, *, activation_ref: str, actor_id: str | None, now: datetime
    ) -> LicenseActivation:
        """Activate one seat against *license_row*.

        Raises:
            SeatLimitReachedError: If every seat is already active.
        """
        active_count = await self._activation_repo.count_active(license_row.id)
        if not has_seat_available(
            seat_limit=license_row.seat_limit, active_activation_count=active_count
        ):
            raise SeatLimitReachedError(license_row.id)

        activation = await self._activation_repo.create(
            LicenseActivation(
                organization_id=license_row.organization_id,
                license_id=license_row.id,
                activation_ref=activation_ref,
                activated_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                license_row.organization_id,
                action=AuditAction.LICENSE_ACTIVATED,
                entity_type="license_activation",
                entity_id=activation.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Activated seat {activation_ref!r} for license {license_row.id!s}.",
            )
        await self._publish(
            LicenseActivatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=license_row.organization_id,
                payload={"license_id": str(license_row.id), "activation_ref": activation_ref},
            )
        )
        return activation

    async def deactivate_seat(
        self, activation: LicenseActivation, *, now: datetime
    ) -> LicenseActivation:
        activation.is_enabled = False
        activation.deactivated_at = now
        return await self._activation_repo.update(activation)


__all__ = ["LicenseService", "SeatLimitReachedError", "TransitionRefusedError"]
