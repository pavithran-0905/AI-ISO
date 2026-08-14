"""Synchronization job enqueueing and offline-queue processing.

**Enqueueing is synchronous; processing is not.** ``POST /mobile/sync``
only creates the job and its queued items, returning immediately -- the
actual work of applying each item (conflict detection, resolution,
retries) belongs exclusively to
:class:`~app.workers.sync_queue_retry_sweep.SyncQueueRetrySweepWorker`,
matching how a real mobile client's own offline queue is drained in
the background rather than blocking the request that enqueued it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.events.domain_events import SynchronizationCompletedEvent, SynchronizationFailedEvent
from app.models.enums import ConflictResolutionStrategy, SyncJobStatus, SyncQueueStatus
from app.models.sync import MobileSyncJob, MobileSyncQueueItem
from app.repositories.sync import MobileSyncJobRepository, MobileSyncQueueItemRepository
from app.sync.engine import (
    TransitionRefusal,
    detect_conflict,
    resolve_conflict,
    validate_job_transition,
    validate_queue_transition,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "mobile-api-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


@dataclass(frozen=True, slots=True)
class SyncItemInput:
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    client_updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobTransitionRefusedError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class SyncService:
    def __init__(
        self,
        jobs_repo: MobileSyncJobRepository,
        queue_repo: MobileSyncQueueItemRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._jobs = jobs_repo
        self._queue = queue_repo
        self._publish = publish

    async def enqueue(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        sync_type: Any,
        items: Sequence[SyncItemInput],
    ) -> MobileSyncJob:
        job = await self._jobs.create(
            MobileSyncJob(
                organization_id=organization_id,
                device_id=device_id,
                sync_type=sync_type,
                item_count=len(items),
            )
        )
        for item in items:
            await self._queue.create(
                MobileSyncQueueItem(
                    organization_id=organization_id,
                    sync_job_id=job.id,
                    device_id=device_id,
                    action_type=item.action_type,
                    payload=item.payload,
                    client_updated_at=item.client_updated_at,
                )
            )
        return job

    async def start_job(self, job: MobileSyncJob, *, now: datetime) -> MobileSyncJob:
        result = validate_job_transition(job.status, SyncJobStatus.RUNNING)
        if not result.is_allowed:
            if result.refusal == TransitionRefusal.TERMINAL_STATE:
                return job  # already finished; nothing to start
            raise JobTransitionRefusedError(result.detail)
        job.status = SyncJobStatus.RUNNING
        job.started_at = now
        return await self._jobs.update(job)

    async def apply_queue_item(
        self,
        item: MobileSyncQueueItem,
        *,
        server_updated_at: datetime | None,
        strategy: ConflictResolutionStrategy,
        now: datetime,
    ) -> MobileSyncQueueItem:
        """Attempt to apply one queued item, resolving any detected
        conflict per *strategy*."""
        target = SyncQueueStatus.PROCESSING
        validation = validate_queue_transition(item.status, target)
        if validation.is_allowed:
            item.status = target
            await self._queue.update(item)

        if detect_conflict(
            client_updated_at=item.client_updated_at, server_updated_at=server_updated_at
        ):
            assert server_updated_at is not None  # detect_conflict guarantees this
            client_wins = resolve_conflict(
                strategy,
                client_updated_at=item.client_updated_at,
                server_updated_at=server_updated_at,
            )
            if strategy == ConflictResolutionStrategy.MANUAL and not client_wins:
                item.status = SyncQueueStatus.CONFLICT
                item.conflict_detail = "manual resolution required"
                item.processed_at = now
                return await self._queue.update(item)
            if not client_wins:
                item.status = SyncQueueStatus.CONFLICT
                item.conflict_detail = f"{strategy.value} resolved against the client's change"
                item.processed_at = now
                return await self._queue.update(item)

        item.status = SyncQueueStatus.APPLIED
        item.processed_at = now
        return await self._queue.update(item)

    async def fail_queue_item(
        self, item: MobileSyncQueueItem, *, detail: str
    ) -> MobileSyncQueueItem:
        item.status = SyncQueueStatus.FAILED
        item.conflict_detail = detail
        item.retry_count += 1
        return await self._queue.update(item)

    async def requeue_item(self, item: MobileSyncQueueItem) -> MobileSyncQueueItem:
        item.status = SyncQueueStatus.QUEUED
        return await self._queue.update(item)

    async def complete_job(
        self, job: MobileSyncJob, *, applied_count: int, now: datetime
    ) -> MobileSyncJob:
        job.status = SyncJobStatus.COMPLETED
        job.applied_count = applied_count
        job.completed_at = now
        job = await self._jobs.update(job)
        await self._publish(
            SynchronizationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "sync_job_id": str(job.id),
                    "device_id": str(job.device_id),
                    "applied_count": applied_count,
                },
            )
        )
        return job

    async def fail_job(
        self,
        job: MobileSyncJob,
        *,
        conflict_count: int,
        reason: str,
        now: datetime,
        device_identifier: str,
    ) -> MobileSyncJob:
        job.status = SyncJobStatus.FAILED
        job.conflict_count = conflict_count
        job.completed_at = now
        job = await self._jobs.update(job)
        await self._publish(
            SynchronizationFailedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "sync_job_id": str(job.id),
                    "device_id": str(job.device_id),
                    "device_identifier": device_identifier,
                    "reason": reason,
                },
            )
        )
        return job


__all__ = ["JobTransitionRefusedError", "SyncItemInput", "SyncService"]
