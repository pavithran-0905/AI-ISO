"""Drift recording and resolution.

Wires ``app.drift.engine``'s pure hash comparison and severity
classification onto the repository that persists drift events,
publishing ``DriftDetected``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.drift.engine import classify_drift_severity, has_drifted
from app.events.domain_events import DriftDetectedEvent
from app.models.enums import DriftStatus
from app.models.operations import CloudDrift
from app.repositories.operations import CloudDriftRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "cloud-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CloudDriftService:
    def __init__(
        self, repo: CloudDriftRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def check(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID,
        desired_state_hash: str | None,
        live_state_hash: str | None,
        drifted_field_count: int,
        high_threshold: int,
        critical_threshold: int,
        now: datetime,
    ) -> CloudDrift | None:
        """Record a drift event for *resource_id* if drifted, returning
        the recorded row, or ``None`` if it did not drift."""
        if not has_drifted(desired_state_hash, live_state_hash):
            return None

        severity = classify_drift_severity(
            drifted_field_count,
            high_threshold=high_threshold,
            critical_threshold=critical_threshold,
        )
        drift = await self._repo.create(
            CloudDrift(
                organization_id=organization_id,
                resource_id=resource_id,
                severity=severity,
                status=DriftStatus.DETECTED,
                desired_state_hash=desired_state_hash,
                live_state_hash=live_state_hash,
                detected_at=now,
            )
        )
        await self._publish(
            DriftDetectedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"resource_id": str(resource_id), "severity": str(severity)},
            )
        )
        return drift

    async def resolve(self, drift: CloudDrift, *, now: datetime) -> CloudDrift:
        drift.status = DriftStatus.RESOLVED
        drift.resolved_at = now
        return await self._repo.update(drift)

    async def acknowledge(self, drift: CloudDrift) -> CloudDrift:
        drift.status = DriftStatus.ACKNOWLEDGED
        return await self._repo.update(drift)


__all__ = ["CloudDriftService"]
