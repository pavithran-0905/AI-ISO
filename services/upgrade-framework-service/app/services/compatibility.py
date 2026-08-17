"""Compatibility matrix validation.

Publishes ``CompatibilityValidated`` on every check, and notifies
Compatibility Issue directly on a non-``PASSED`` outcome.
"""

from __future__ import annotations

from uuid import UUID

from app.compatibility.engine import classify_compatibility
from app.events.domain_events import CompatibilityValidatedEvent
from app.models.compatibility import CompatibilityMatrixEntry
from app.models.enums import CheckResultStatus, CompatibilityType
from app.repositories.compatibility import CompatibilityMatrixRepository
from app.services.notifications import UpgradeNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "upgrade-framework-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CompatibilityService:
    def __init__(
        self,
        repo: CompatibilityMatrixRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: UpgradeNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def validate(
        self,
        organization_id: UUID,
        *,
        from_version: str,
        to_version: str,
        compatibility_type: CompatibilityType,
        detail: str = "",
    ) -> CompatibilityMatrixEntry:
        status = classify_compatibility(from_version=from_version, to_version=to_version)
        existing = await self._repo.find_entry(
            organization_id,
            from_version=from_version,
            to_version=to_version,
            compatibility_type=compatibility_type,
        )
        if existing is not None:
            existing.status = status
            existing.detail = detail
            entry = await self._repo.update(existing)
        else:
            entry = await self._repo.create(
                CompatibilityMatrixEntry(
                    organization_id=organization_id,
                    from_version=from_version,
                    to_version=to_version,
                    compatibility_type=compatibility_type,
                    status=status,
                    detail=detail,
                )
            )
        await self._publish(
            CompatibilityValidatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"compatibility_type": compatibility_type.value, "status": status.value},
            )
        )
        if status != CheckResultStatus.PASSED and self._notifier is not None:
            await self._notifier.notify_compatibility_issue(
                compatibility_type=compatibility_type.value, detail=detail
            )
        return entry


__all__ = ["CompatibilityService"]
