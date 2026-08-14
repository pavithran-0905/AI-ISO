"""The sync queue retry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**This is the only place offline actions actually get applied.**
``POST /mobile/sync`` only enqueues a job and its queue items and
returns immediately -- draining that queue is exclusively this
worker's job, matching a real mobile client's own background sync.

**Conflict detection is honest about what this service can actually
know.** This service does not own the arbitrary downstream AI-IOS
resources a queued action ultimately targets (calling out to whichever
service does is a declared-out-of-scope integration, per docs/072 "DO
NOT IMPLEMENT"), so it has no independent way to learn a resource's own
current ``server_updated_at``. A queued item's own ``payload`` may
optionally carry a ``server_updated_at`` ISO-8601 hint (in a full
deployment, populated by whatever call this worker would make to the
owning service); when absent, the item is applied with no conflict, since
there is nothing this service could truthfully detect a conflict against.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from shared_core.database.tenant import TenantScope
from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.domain_events import OfflineQueueProcessedEvent
from app.models.enums import ConflictResolutionStrategy, SyncQueueStatus
from app.models.sync import MobileSyncQueueItem
from app.services.bundle import build_repositories
from app.services.sync import SyncService
from app.types import EventPublisher

logger = get_logger("app.workers.sync_queue_retry_sweep")

_SOURCE_SERVICE = "mobile-api-service"
_MAX_ITEMS_PER_TICK = 1_000


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


def _parse_server_updated_at(payload: dict[str, object]) -> datetime | None:
    raw = payload.get("server_updated_at")
    if not isinstance(raw, str):
        return None
    return datetime.fromisoformat(raw)


class SyncQueueRetrySweepWorker:
    """Drains every organization's queued offline actions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher = _noop_publisher,
        conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.SERVER_WINS,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._conflict_strategy = conflict_strategy

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Process every organization's queued items, returning how
        many were processed."""
        now = datetime.now(UTC)
        processed = 0

        async with self._session_factory() as session:
            unscoped_repos = build_repositories(session)
            organization_ids = await unscoped_repos.sync_queue.list_organization_ids()

            for organization_id in organization_ids:
                processed += await self._process_organization(session, organization_id, now=now)
            await session.commit()

        logger.info(
            "sync queue retry sweep completed", extra={"extra_fields": {"processed": processed}}
        )
        return processed

    async def _process_organization(
        self, session: AsyncSession, organization_id: UUID, *, now: datetime
    ) -> int:
        repos = build_repositories(
            session, tenant_scope=TenantScope(organization_id=organization_id)
        )
        sync_service = SyncService(repos.sync_jobs, repos.sync_queue, publish=self._publish)

        queued_items = await repos.sync_queue.list_queued(
            organization_id, limit=_MAX_ITEMS_PER_TICK
        )
        items_by_job: dict[UUID, list[MobileSyncQueueItem]] = defaultdict(list)
        for item in queued_items:
            items_by_job[item.sync_job_id].append(item)

        processed = 0
        for sync_job_id, job_items in items_by_job.items():
            job = await repos.sync_jobs.get_by_id(sync_job_id)
            if job is None:
                continue
            job = await sync_service.start_job(job, now=now)

            for item in job_items:
                server_updated_at = _parse_server_updated_at(item.payload)
                await sync_service.apply_queue_item(
                    item,
                    server_updated_at=server_updated_at,
                    strategy=self._conflict_strategy,
                    now=now,
                )
                processed += 1

            remaining = await repos.sync_queue.list_for_job(job.id)
            if any(row.status == SyncQueueStatus.QUEUED for row in remaining):
                continue  # more items still queued for this job; finish it on a later tick

            applied_count = sum(1 for row in remaining if row.status == SyncQueueStatus.APPLIED)
            conflict_count = sum(1 for row in remaining if row.status == SyncQueueStatus.CONFLICT)
            failed_count = sum(1 for row in remaining if row.status == SyncQueueStatus.FAILED)

            device = await repos.devices.get_by_id(job.device_id)
            device_identifier = device.device_identifier if device is not None else "unknown"

            if conflict_count > 0 or failed_count > 0:
                job = await sync_service.fail_job(
                    job,
                    conflict_count=conflict_count,
                    reason=f"{conflict_count} conflict(s), {failed_count} failure(s)",
                    now=now,
                    device_identifier=device_identifier,
                )
            else:
                job = await sync_service.complete_job(job, applied_count=applied_count, now=now)

            await self._publish(
                OfflineQueueProcessedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=organization_id,
                    payload={"device_id": str(job.device_id), "processed_count": len(remaining)},
                )
            )
        return processed


__all__ = ["SyncQueueRetrySweepWorker"]
