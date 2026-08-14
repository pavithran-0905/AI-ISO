"""Device synchronization execution, conflict resolution, and retry.

Wires ``app.synchronization.engine``'s pure conflict resolution and
retry decision, and ``app.store_forward.engine``'s pure backoff
calculation, onto the repository that persists sync executions,
publishing ``SynchronizationCompleted``/``SynchronizationFailed``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import SynchronizationCompletedEvent, SynchronizationFailedEvent
from app.models.enums import ConflictResolutionStrategy, SyncKind, SyncStatus
from app.models.operations import EdgeSynchronization
from app.repositories.operations import EdgeSynchronizationRepository
from app.store_forward.engine import compute_backoff_seconds
from app.synchronization.engine import (
    ConflictWinner,
    RetryDecision,
    resolve_conflict,
    should_retry_sync,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "edge-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SynchronizationService:
    def __init__(
        self, repo: EdgeSynchronizationRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def start_sync(
        self, organization_id: UUID, *, device_id: UUID, sync_kind: SyncKind, now: datetime
    ) -> EdgeSynchronization:
        return await self._repo.create(
            EdgeSynchronization(
                organization_id=organization_id,
                device_id=device_id,
                sync_kind=sync_kind,
                status=SyncStatus.IN_PROGRESS,
                started_at=now,
            )
        )

    async def complete_sync(
        self, sync: EdgeSynchronization, *, bytes_transferred: int | None, now: datetime
    ) -> EdgeSynchronization:
        sync.status = SyncStatus.COMPLETED
        sync.completed_at = now
        sync.bytes_transferred = bytes_transferred
        sync.duration_ms = (
            (now - sync.started_at).total_seconds() * 1000.0 if sync.started_at else None
        )
        await self._repo.update(sync)
        await self._publish(
            SynchronizationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=sync.organization_id,
                payload={
                    "device_id": str(sync.device_id),
                    "sync_id": str(sync.id),
                    "sync_kind": str(sync.sync_kind),
                    "duration_ms": sync.duration_ms,
                },
            )
        )
        return sync

    async def fail_sync(
        self, sync: EdgeSynchronization, *, error_message: str, now: datetime
    ) -> EdgeSynchronization:
        sync.status = SyncStatus.FAILED
        sync.completed_at = now
        sync.error_message = error_message
        await self._repo.update(sync)
        await self._publish(
            SynchronizationFailedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=sync.organization_id,
                payload={
                    "device_id": str(sync.device_id),
                    "sync_id": str(sync.id),
                    "error_message": error_message,
                },
            )
        )
        return sync

    async def mark_conflict(
        self, sync: EdgeSynchronization, *, resolution: ConflictResolutionStrategy, now: datetime
    ) -> tuple[EdgeSynchronization, str]:
        """Mark *sync* conflicted and resolve it per *resolution*.

        Returns the updated sync and the resolved
        :class:`~app.synchronization.engine.ConflictWinner`.
        """
        sync.status = SyncStatus.CONFLICT
        sync.conflict_resolution = resolution
        sync.completed_at = now
        await self._repo.update(sync)
        winner = resolve_conflict(resolution, server_updated_at=now, device_updated_at=now)
        return sync, winner

    def decide_retry(
        self, sync: EdgeSynchronization, *, attempt_count: int, max_attempts: int
    ) -> RetryDecision:
        return should_retry_sync(
            sync.status, attempt_count=attempt_count, max_attempts=max_attempts
        )

    def next_retry_delay_seconds(
        self, *, attempt_count: int, base_seconds: float = 5.0, max_seconds: float = 3600.0
    ) -> float:
        return compute_backoff_seconds(
            attempt_count, base_seconds=base_seconds, max_seconds=max_seconds
        )


__all__ = ["ConflictWinner", "SynchronizationService"]
