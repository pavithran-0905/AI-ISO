"""Rolled-up statistics, generated reports, and the immutable audit
trail.

The audit trail is append-only by convention and by absence: there is no
update path to it anywhere in this service, matching
``services/backup-dr-service``'s ``BackupAudit`` precedent exactly.
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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import AuditAction, ReportFormat, ReportKind, ReportStatus


class EdgeStatistic(BaseModel):
    """``edge_statistics`` -- one rolled-up fleet-wide window.

    Idempotent per window, matching every other AI-IOS statistics table:
    the worker updates the row for a window rather than inserting a
    second, so a retried rollup cannot double-count.
    """

    __tablename__ = "edge_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "window_start", name="uq_edge_statistic_window"),
        Index("ix_edge_statistic_window", "window_start"),
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    sites_registered: Mapped[int] = mapped_column(Integer, default=0)
    devices_online: Mapped[int] = mapped_column(Integer, default=0)
    devices_offline: Mapped[int] = mapped_column(Integer, default=0)
    synchronizations_completed: Mapped[int] = mapped_column(Integer, default=0)
    synchronizations_failed: Mapped[int] = mapped_column(Integer, default=0)
    updates_completed: Mapped[int] = mapped_column(Integer, default=0)
    updates_failed: Mapped[int] = mapped_column(Integer, default=0)


class EdgeReport(BaseModel):
    """``edge_reports`` -- one generated report."""

    __tablename__ = "edge_reports"
    __table_args__ = (
        Index("ix_edge_report_kind", "kind"),
        Index("ix_edge_report_status", "status"),
    )

    kind: Mapped[ReportKind] = mapped_column(String(24), index=True)
    report_format: Mapped[ReportFormat] = mapped_column(String(16), default=ReportFormat.JSON)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[ReportStatus] = mapped_column(
        String(16), default=ReportStatus.PENDING, index=True
    )

    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    content: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)

    generated_by: Mapped[str | None] = mapped_column(String(128), default=None)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class EdgeAudit(BaseModel):
    """``edge_audit`` -- the immutable trail.

    Every site registration, device registration, configuration change,
    OTA update, remote access, policy change, and administrative
    operation is recorded here, per docs/067's own AUDIT section.
    """

    __tablename__ = "edge_audit"
    __table_args__ = (
        Index("ix_edge_audit_time", "occurred_at"),
        Index("ix_edge_audit_action", "action"),
        Index("ix_edge_audit_actor", "actor_id"),
    )

    action: Mapped[AuditAction] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    entity_reference: Mapped[str | None] = mapped_column(String(512), default=None)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    summary: Mapped[str | None] = mapped_column(String(512), default=None)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = ["EdgeAudit", "EdgeReport", "EdgeStatistic"]
