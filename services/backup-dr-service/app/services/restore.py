"""Restore execution: point selection, preview, and the job lifecycle.

Wires ``app.restore.engine``'s pure point-selection and preview logic
onto the repositories that persist restore jobs and points.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import RestoreCompletedEvent, RestoreStartedEvent
from app.models.enums import RestoreJobStatus, RestoreKind
from app.models.recovery import RestoreJob, RestorePoint
from app.repositories.recovery import RestoreJobRepository, RestorePointRepository
from app.restore.engine import (
    PointSelection,
    RestorePointCandidate,
    RestorePreview,
    build_preview,
    select_restore_point,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "backup-dr-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


def _to_candidate(row: RestorePoint) -> RestorePointCandidate:
    return RestorePointCandidate(
        point_id=str(row.id),
        available_at=row.available_at,
        is_available=row.is_available,
        expires_at=row.expires_at,
        source_archive_id=str(row.source_archive_id) if row.source_archive_id else None,
    )


class RestoreService:
    """Selects restore points, previews restores, and runs restore jobs."""

    def __init__(
        self,
        job_repo: RestoreJobRepository,
        point_repo: RestorePointRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._job_repo = job_repo
        self._point_repo = point_repo
        self._publish = publish

    async def select_point(
        self, target_id: UUID, *, requested_at: datetime, now: datetime
    ) -> PointSelection:
        rows = await self._point_repo.list_for_target(target_id)
        candidates = [_to_candidate(row) for row in rows]
        return select_restore_point(requested_at, candidates, now=now)

    def preview(
        self,
        *,
        restore_kind: RestoreKind,
        source_ref: str,
        target_ref: str,
        source_ref_equals_original: bool,
        estimated_size_bytes: int | None,
    ) -> RestorePreview:
        return build_preview(
            restore_kind=restore_kind.value,
            source_ref=source_ref,
            target_ref=target_ref,
            source_ref_equals_original=source_ref_equals_original,
            estimated_size_bytes=estimated_size_bytes,
        )

    async def start_job(
        self,
        organization_id: UUID,
        *,
        source_archive_id: UUID | None,
        restore_point_id: UUID | None,
        restore_kind: RestoreKind,
        target_ref: str | None,
        is_preview: bool,
        requested_by: str | None,
        now: datetime,
    ) -> RestoreJob:
        job = await self._job_repo.create(
            RestoreJob(
                organization_id=organization_id,
                source_archive_id=source_archive_id,
                restore_point_id=restore_point_id,
                restore_kind=restore_kind,
                target_ref=target_ref,
                status=RestoreJobStatus.PREVIEWING if is_preview else RestoreJobStatus.RUNNING,
                is_preview=is_preview,
                requested_by=requested_by,
                started_at=now,
            )
        )
        await self._publish(
            RestoreStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "restore_job_id": str(job.id),
                    "restore_kind": str(restore_kind),
                    "is_preview": is_preview,
                },
            )
        )
        return job

    async def complete_job(
        self, job: RestoreJob, *, is_validated: bool, validation_summary: str | None, now: datetime
    ) -> RestoreJob:
        job.status = RestoreJobStatus.VALIDATED if is_validated else RestoreJobStatus.COMPLETED
        job.completed_at = now
        job.duration_ms = (
            (now - job.started_at).total_seconds() * 1000.0 if job.started_at else None
        )
        job.is_validated = is_validated
        job.validation_summary = validation_summary
        await self._job_repo.update(job)
        await self._publish(
            RestoreCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "restore_job_id": str(job.id),
                    "status": str(job.status),
                    "duration_ms": job.duration_ms,
                },
            )
        )
        return job

    async def fail_job(self, job: RestoreJob, *, error_message: str, now: datetime) -> RestoreJob:
        job.status = RestoreJobStatus.FAILED
        job.completed_at = now
        job.error_message = error_message
        await self._job_repo.update(job)
        await self._publish(
            RestoreCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "restore_job_id": str(job.id),
                    "status": str(job.status),
                    "duration_ms": None,
                },
            )
        )
        return job


__all__ = ["RestoreService"]
