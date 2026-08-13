"""The backup-side tables: targets, schedules, jobs, snapshots, archives,
retention policy, and verification.

**A backup job's completion and its verification are separate rows.**
:class:`BackupVerification` is never inferred from
:attr:`BackupJob.status` alone -- a job that finished writing every byte
can still be unreadable, and "we wrote it" and "we proved it reads back"
are different claims with different evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    BackupJobStatus,
    BackupTargetKind,
    BackupType,
    ConsistencyLevel,
    ImmutabilityState,
    RetentionTier,
    ScheduleFrequency,
    SnapshotKind,
    SnapshotStatus,
    VerificationKind,
    VerificationStatus,
)


class BackupTarget(BaseModel):
    """``backup_targets`` -- one thing this service knows how to back up.

    ``connection_ref`` is a lookup key into secrets-management-service,
    never a raw credential -- this service orchestrates backups, it does
    not become a second place secrets can leak from.
    """

    __tablename__ = "backup_targets"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_backup_target_name"),
        Index("ix_backup_target_kind", "target_kind"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    target_kind: Mapped[BackupTargetKind] = mapped_column(String(32), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")
    connection_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_backup_status: Mapped[BackupJobStatus | None] = mapped_column(String(16), default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class BackupSchedule(BaseModel):
    """``backup_schedules`` -- when a target is backed up, and how."""

    __tablename__ = "backup_schedules"
    __table_args__ = (Index("ix_backup_schedule_target", "target_id"),)

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_targets.id", ondelete="CASCADE"), index=True
    )
    backup_type: Mapped[BackupType] = mapped_column(String(24))
    consistency_level: Mapped[ConsistencyLevel] = mapped_column(
        String(24), default=ConsistencyLevel.CRASH_CONSISTENT
    )
    frequency: Mapped[ScheduleFrequency] = mapped_column(String(16))
    cron_expression: Mapped[str | None] = mapped_column(String(128), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, default=None
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)


class BackupJob(BaseModel):
    """``backup_jobs`` -- one execution of a backup, scheduled or manual.

    ``parent_job_id`` chains an incremental to the backup it is
    incremental *against* -- never assumed to be "whatever ran last",
    since a failed intervening job would silently break the chain a
    restore later depends on.
    """

    __tablename__ = "backup_jobs"
    __table_args__ = (
        Index("ix_backup_job_target", "target_id"),
        Index("ix_backup_job_status", "status"),
        Index("ix_backup_job_started", "started_at"),
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_targets.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_schedules.id", ondelete="SET NULL"), default=None, index=True
    )
    parent_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_jobs.id", ondelete="SET NULL"), default=None, index=True
    )

    backup_type: Mapped[BackupType] = mapped_column(String(24))
    consistency_level: Mapped[ConsistencyLevel] = mapped_column(
        String(24), default=ConsistencyLevel.UNKNOWN
    )
    status: Mapped[BackupJobStatus] = mapped_column(
        String(16), default=BackupJobStatus.PENDING, index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)

    size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    compressed_size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    """``None`` until the job finishes -- a size reported mid-transfer is
    not the backup's size, it is a partial count that will be wrong by
    definition the moment the transfer continues."""

    checksum: Mapped[str | None] = mapped_column(String(128), default=None)
    checksum_algorithm: Mapped[str | None] = mapped_column(String(16), default=None)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    encryption_key_ref: Mapped[str | None] = mapped_column(String(255), default=None)

    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class BackupSnapshot(BaseModel):
    """``backup_snapshots`` -- a point-in-time storage-layer snapshot,
    distinct from a :class:`BackupJob`'s streamed archive."""

    __tablename__ = "backup_snapshots"
    __table_args__ = (
        Index("ix_backup_snapshot_target", "target_id"),
        Index("ix_backup_snapshot_status", "status"),
        Index("ix_backup_snapshot_expires", "expires_at"),
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_targets.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_jobs.id", ondelete="SET NULL"), default=None, index=True
    )
    snapshot_kind: Mapped[SnapshotKind] = mapped_column(String(32))
    status: Mapped[SnapshotStatus] = mapped_column(String(16), default=SnapshotStatus.PENDING)

    storage_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)

    created_at_source: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """When the underlying storage layer took the snapshot -- distinct
    from ``BaseModel.created_at``, which is when this row was written and
    may lag the real snapshot instant by however long ingestion took."""
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)


class BackupArchive(BaseModel):
    """``backup_archives`` -- a job's output at rest, with its
    immutability and lifecycle state.

    ``retention_lock_until`` is enforced at the storage layer, not just
    read here: a lock this row cannot see past is what makes "immutable"
    mean something against an attacker who also has database access.
    """

    __tablename__ = "backup_archives"
    __table_args__ = (
        Index("ix_backup_archive_job", "job_id"),
        Index("ix_backup_archive_tier", "tier"),
        Index("ix_backup_archive_immutability", "immutability_state"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_jobs.id", ondelete="CASCADE"), index=True
    )
    storage_ref: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128), default=None)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    encryption_key_ref: Mapped[str | None] = mapped_column(String(255), default=None)

    tier: Mapped[RetentionTier] = mapped_column(String(16), default=RetentionTier.HOT, index=True)
    immutability_state: Mapped[ImmutabilityState] = mapped_column(
        String(24), default=ImmutabilityState.NONE, index=True
    )
    retention_lock_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(String(512), default=None)

    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_deleted_from_storage: Mapped[bool] = mapped_column(Boolean, default=False)


class BackupRetention(BaseModel):
    """``backup_retention`` -- how long backups for one scope are kept,
    at what tier, before archival and eventual deletion.

    Scoped by ``target_kind`` (``None`` means "every target kind not
    otherwise covered") rather than by individual target, so a new
    target inherits a sane default the moment it is registered instead
    of starting with no retention policy at all.
    """

    __tablename__ = "backup_retention"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "target_kind", "environment", name="uq_backup_retention_scope"
        ),
    )

    target_kind: Mapped[BackupTargetKind | None] = mapped_column(
        String(32), default=None, index=True
    )
    environment: Mapped[str] = mapped_column(String(64), default="production")

    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    archive_after_days: Mapped[int] = mapped_column(Integer, default=30)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_purged_count: Mapped[int | None] = mapped_column(Integer, default=None)


class BackupVerification(BaseModel):
    """``backup_verifications`` -- proof (or disproof) that a backup is
    actually usable, kept apart from the job it verifies."""

    __tablename__ = "backup_verifications"
    __table_args__ = (
        Index("ix_backup_verification_job", "job_id"),
        Index("ix_backup_verification_status", "status"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_jobs.id", ondelete="CASCADE"), index=True
    )
    archive_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_archives.id", ondelete="SET NULL"), default=None
    )
    verification_kind: Mapped[VerificationKind] = mapped_column(String(24))
    status: Mapped[VerificationStatus] = mapped_column(
        String(16), default=VerificationStatus.PENDING, index=True
    )

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    checksum_expected: Mapped[str | None] = mapped_column(String(128), default=None)
    checksum_actual: Mapped[str | None] = mapped_column(String(128), default=None)
    sample_restore_job_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


__all__ = [
    "BackupArchive",
    "BackupJob",
    "BackupRetention",
    "BackupSchedule",
    "BackupSnapshot",
    "BackupTarget",
    "BackupVerification",
]
