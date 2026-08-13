"""Backup orchestration: targets, schedules, and the job lifecycle.

Wires ``app.backup.engine``'s pure chain validation, deduplication, and
scheduling onto the repositories that persist jobs, and publishes the
three job-lifecycle events docs/065 names.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.backup.engine import ChainLink, compute_next_run, detect_duplicate, validate_chain
from app.events.domain_events import BackupCompletedEvent, BackupFailedEvent, BackupStartedEvent
from app.models.backup import BackupJob, BackupSchedule, BackupTarget
from app.models.enums import AuditAction, BackupJobStatus, BackupType
from app.repositories.backup import (
    BackupJobRepository,
    BackupScheduleRepository,
    BackupTargetRepository,
)
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "backup-dr-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class BackupTargetService:
    """Registers and looks up things this service can back up."""

    def __init__(self, repo: BackupTargetRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def register_target(
        self,
        organization_id: UUID,
        *,
        name: str,
        target_kind: str,
        environment: str,
        connection_ref: str | None,
        actor_id: str | None,
        now: datetime,
    ) -> BackupTarget:
        target = await self._repo.create(
            BackupTarget(
                organization_id=organization_id,
                name=name,
                target_kind=target_kind,
                environment=environment,
                connection_ref=connection_ref,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.ADMINISTRATIVE,
                entity_type="backup_target",
                entity_id=target.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Registered backup target {name!r} ({target_kind}).",
            )
        return target


class BackupScheduleService:
    """Creates schedules and computes when they next fire."""

    def __init__(
        self, repo: BackupScheduleRepository, *, audit: AuditService | None = None
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def create_schedule(
        self,
        organization_id: UUID,
        *,
        target_id: UUID,
        backup_type: BackupType,
        frequency: str,
        cron_expression: str | None,
        retention_days: int,
        actor_id: str | None,
        now: datetime,
    ) -> BackupSchedule:
        next_run = (
            None
            if frequency == "custom_cron"
            else compute_next_run(frequency, last_run_at=None, now=now)
        )
        schedule = await self._repo.create(
            BackupSchedule(
                organization_id=organization_id,
                target_id=target_id,
                backup_type=backup_type,
                frequency=frequency,
                cron_expression=cron_expression,
                retention_days=retention_days,
                next_run_at=next_run,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.BACKUP_CONFIGURED,
                entity_type="backup_schedule",
                entity_id=schedule.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=(
                    f"Created {frequency} {backup_type.value} schedule for target {target_id!s}."
                ),
            )
        return schedule


class BackupJobService:
    """Runs one backup job's lifecycle: start, complete (with chain
    validation and dedup), or fail."""

    def __init__(
        self,
        repo: BackupJobRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def start_job(
        self,
        organization_id: UUID,
        *,
        target: BackupTarget,
        backup_type: BackupType,
        schedule_id: UUID | None,
        parent_job_id: UUID | None,
        now: datetime,
    ) -> BackupJob:
        job = await self._repo.create(
            BackupJob(
                organization_id=organization_id,
                target_id=target.id,
                schedule_id=schedule_id,
                parent_job_id=parent_job_id,
                backup_type=backup_type,
                status=BackupJobStatus.RUNNING,
                started_at=now,
            )
        )
        await self._publish(
            BackupStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "job_id": str(job.id),
                    "target_id": str(target.id),
                    "target_name": target.name,
                    "backup_type": str(backup_type),
                },
            )
        )
        return job

    async def complete_job(
        self,
        job: BackupJob,
        *,
        size_bytes: int,
        checksum: str,
        checksum_algorithm: str,
        chain: list[ChainLink] | None,
        existing_checksums: list[tuple[str, str, int]],
        now: datetime,
    ) -> BackupJob:
        """Complete a job, validating its chain (for incremental/
        differential backups) and checking for duplicate content first.

        A job whose chain does not validate is marked ``FAILED``, never
        ``COMPLETED`` with a note -- a restore planner trusts
        ``COMPLETED`` to mean the chain is walkable, and a broken chain
        marked complete is discovered only when a restore needs it.
        """
        if chain is not None:
            validation = validate_chain(
                str(job.id),
                [
                    *chain,
                    ChainLink(
                        job_id=str(job.id),
                        backup_type=job.backup_type,
                        parent_job_id=str(job.parent_job_id) if job.parent_job_id else None,
                        status=BackupJobStatus.COMPLETED,
                        completed_at=now,
                    ),
                ],
            )
            if not validation.is_intact:
                return await self.fail_job(
                    job,
                    error_message=f"Chain validation failed: {validation.break_reason}",
                    now=now,
                )

        dedupe = detect_duplicate(checksum, size_bytes, existing_checksums)
        job.status = BackupJobStatus.COMPLETED
        job.completed_at = now
        job.duration_ms = (
            (now - job.started_at).total_seconds() * 1000.0 if job.started_at else None
        )
        job.size_bytes = size_bytes
        job.checksum = checksum
        job.checksum_algorithm = checksum_algorithm
        if dedupe.is_duplicate:
            job.details = {**job.details, "duplicate_of_job_id": dedupe.duplicate_of_job_id}
        await self._repo.update(job)

        await self._publish(
            BackupCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "job_id": str(job.id),
                    "target_id": str(job.target_id),
                    "size_bytes": size_bytes,
                    "duration_ms": job.duration_ms,
                },
            )
        )
        return job

    async def fail_job(self, job: BackupJob, *, error_message: str, now: datetime) -> BackupJob:
        job.status = BackupJobStatus.FAILED
        job.completed_at = now
        job.error_message = error_message
        await self._repo.update(job)
        await self._publish(
            BackupFailedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "job_id": str(job.id),
                    "target_id": str(job.target_id),
                    "error_message": error_message,
                },
            )
        )
        return job


__all__ = ["BackupJobService", "BackupScheduleService", "BackupTargetService"]
