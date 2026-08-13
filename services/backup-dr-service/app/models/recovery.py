"""The recovery-side tables: restore, replication, DR plans, DR tests,
failover events, and recovery reports.

**A DR plan's RPO/RTO targets and its actually-achieved figures are
different rows, in different tables.** :class:`DrTest` and
:class:`RecoveryReport` record what a real drill measured;
:class:`DrPlan` records what was promised. A plan whose targets have
never been checked against a measurement is exactly the failure mode
``ComplianceStatus.NOT_MEASURED`` exists to name rather than hide behind
a plan that merely exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    ComplianceStatus,
    DrPlanStatus,
    DrTestKind,
    DrTestStatus,
    FailoverKind,
    FailoverStatus,
    RecoveryPriority,
    ReplicationMode,
    ReplicationScope,
    ReplicationStatus,
    RestoreJobStatus,
    RestoreKind,
    RestorePointKind,
)


class RestorePoint(BaseModel):
    """``restore_points`` -- one instant a target can be restored to.

    Distinct from the backup or snapshot it was derived from: several
    restore points (every WAL boundary between two backups) can share
    one source archive, and each has its own availability window.
    """

    __tablename__ = "restore_points"
    __table_args__ = (
        Index("ix_restore_point_target", "target_id"),
        Index("ix_restore_point_available_at", "available_at"),
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_targets.id", ondelete="CASCADE"), index=True
    )
    point_kind: Mapped[RestorePointKind] = mapped_column(String(24))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    """The instant on the *target's own timeline* this point restores to
    -- never this row's ``created_at``, which is merely when the
    catalogue learned about it."""
    source_archive_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_archives.id", ondelete="SET NULL"), default=None
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class RestoreJob(BaseModel):
    """``restore_jobs`` -- one restore execution, preview or real."""

    __tablename__ = "restore_jobs"
    __table_args__ = (
        Index("ix_restore_job_status", "status"),
        Index("ix_restore_job_archive", "source_archive_id"),
    )

    source_archive_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_archives.id", ondelete="SET NULL"), default=None, index=True
    )
    restore_point_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restore_points.id", ondelete="SET NULL"), default=None
    )
    restore_kind: Mapped[RestoreKind] = mapped_column(String(24))
    target_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    """Where the restored data is being written -- a new target, not
    necessarily the original one: restoring into a scratch environment
    to inspect a table is a legitimate, common request this field has to
    distinguish from an in-place disaster restore."""

    status: Mapped[RestoreJobStatus] = mapped_column(
        String(16), default=RestoreJobStatus.PENDING, index=True
    )
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_by: Mapped[str | None] = mapped_column(String(128), default=None)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)

    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class ReplicationJob(BaseModel):
    """``replication_jobs`` -- one target's ongoing replication to one
    destination."""

    __tablename__ = "replication_jobs"
    __table_args__ = (
        Index("ix_replication_job_target", "target_id"),
        Index("ix_replication_job_status", "status"),
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backup_targets.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[ReplicationMode] = mapped_column(String(16))
    scope: Mapped[ReplicationScope] = mapped_column(String(16))
    destination_ref: Mapped[str] = mapped_column(String(512))

    status: Mapped[ReplicationStatus] = mapped_column(
        String(16), default=ReplicationStatus.PENDING, index=True
    )
    lag_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    """``None`` when nothing has synced yet -- a lag of zero would claim
    the replica is caught up, which is a different, false statement."""
    bandwidth_limit_mbps: Mapped[float | None] = mapped_column(Float, default=None)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class DrPlan(BaseModel):
    """``dr_plans`` -- a named, versioned recovery strategy.

    ``recovery_groups`` and ``dependencies`` are stored as JSON rather
    than normalised tables on purpose: a plan's structure is authored
    and reviewed as one document, and splitting it across join tables
    would let a partial edit leave the sequencing inconsistent with
    nothing enforcing it.
    """

    __tablename__ = "dr_plans"
    __table_args__ = (Index("ix_dr_plan_status", "status"),)

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[DrPlanStatus] = mapped_column(String(16), default=DrPlanStatus.DRAFT, index=True)
    priority: Mapped[RecoveryPriority] = mapped_column(String(16), default=RecoveryPriority.MEDIUM)

    rpo_minutes: Mapped[int] = mapped_column(Integer, default=60)
    rto_minutes: Mapped[int] = mapped_column(Integer, default=120)

    recovery_groups: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """Ordered list of ``{name, target_ids, depends_on}`` -- the
    sequencing a real failover walks, group by group."""
    dependencies: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped[str | None] = mapped_column(String(128), default=None)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class DrTest(BaseModel):
    """``dr_tests`` -- one drill against one plan, with what it actually
    measured."""

    __tablename__ = "dr_tests"
    __table_args__ = (
        Index("ix_dr_test_plan", "dr_plan_id"),
        Index("ix_dr_test_status", "status"),
    )

    dr_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dr_plans.id", ondelete="CASCADE"), index=True
    )
    test_kind: Mapped[DrTestKind] = mapped_column(String(16))
    status: Mapped[DrTestStatus] = mapped_column(
        String(16), default=DrTestStatus.SCHEDULED, index=True
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)

    achieved_rpo_minutes: Mapped[float | None] = mapped_column(Float, default=None)
    achieved_rto_minutes: Mapped[float | None] = mapped_column(Float, default=None)
    rpo_status: Mapped[ComplianceStatus] = mapped_column(
        String(16), default=ComplianceStatus.NOT_MEASURED
    )
    rto_status: Mapped[ComplianceStatus] = mapped_column(
        String(16), default=ComplianceStatus.NOT_MEASURED
    )

    findings: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, default=None)


class FailoverEvent(BaseModel):
    """``failover_events`` -- one failover or failback execution."""

    __tablename__ = "failover_events"
    __table_args__ = (
        Index("ix_failover_event_plan", "dr_plan_id"),
        Index("ix_failover_event_status", "status"),
    )

    dr_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dr_plans.id", ondelete="SET NULL"), default=None, index=True
    )
    failover_kind: Mapped[FailoverKind] = mapped_column(String(16))
    status: Mapped[FailoverStatus] = mapped_column(
        String(16), default=FailoverStatus.INITIATED, index=True
    )

    source_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    target_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    initiated_by: Mapped[str | None] = mapped_column(String(128), default=None)

    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)

    health_check_results: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    was_rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class RecoveryReport(BaseModel):
    """``recovery_reports`` -- the compliance-facing summary of one DR
    test or failover: what was promised versus what happened."""

    __tablename__ = "recovery_reports"
    __table_args__ = (Index("ix_recovery_report_compliance", "compliance_status"),)

    dr_test_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dr_tests.id", ondelete="SET NULL"), default=None, index=True
    )
    failover_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("failover_events.id", ondelete="SET NULL"), default=None, index=True
    )

    rpo_target_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    rpo_achieved_minutes: Mapped[float | None] = mapped_column(Float, default=None)
    rto_target_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    rto_achieved_minutes: Mapped[float | None] = mapped_column(Float, default=None)
    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        String(16), default=ComplianceStatus.NOT_MEASURED, index=True
    )

    summary: Mapped[str | None] = mapped_column(Text, default=None)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = [
    "DrPlan",
    "DrTest",
    "FailoverEvent",
    "RecoveryReport",
    "ReplicationJob",
    "RestoreJob",
    "RestorePoint",
]
