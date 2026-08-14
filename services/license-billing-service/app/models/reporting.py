"""Rolled-up billing statistics, generated reports, and the immutable
audit trail.

The audit trail is append-only by convention and by absence: there is
no update path to it anywhere in this service, matching
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


class BillingStatistic(BaseModel):
    """``billing_statistics`` -- one rolled-up fleet-wide window.

    Idempotent per window, matching every other AI-IOS statistics
    table: the worker updates the row for a window rather than
    inserting a second, so a retried rollup cannot double-count.
    """

    __tablename__ = "billing_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "window_start", name="uq_billing_statistic_window"),
        Index("ix_billing_statistic_window", "window_start"),
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    mrr: Mapped[float] = mapped_column(Float, default=0.0)
    arr: Mapped[float] = mapped_column(Float, default=0.0)
    active_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    churned_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    invoices_generated: Mapped[int] = mapped_column(Integer, default=0)
    payments_received: Mapped[int] = mapped_column(Integer, default=0)
    payments_failed: Mapped[int] = mapped_column(Integer, default=0)
    quota_exceeded_count: Mapped[int] = mapped_column(Integer, default=0)


class BillingReport(BaseModel):
    """``billing_reports`` -- one generated report."""

    __tablename__ = "billing_reports"
    __table_args__ = (
        Index("ix_billing_report_kind", "kind"),
        Index("ix_billing_report_status", "status"),
    )

    kind: Mapped[ReportKind] = mapped_column(String(16), index=True)
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


class BillingAudit(BaseModel):
    """``billing_audit`` -- the immutable trail.

    Every license creation/activation, subscription change, billing
    change, invoice generation, payment event, contract change, and
    administrative operation is recorded here, per docs/069's own
    AUDIT section.
    """

    __tablename__ = "billing_audit"
    __table_args__ = (
        Index("ix_billing_audit_time", "occurred_at"),
        Index("ix_billing_audit_action", "action"),
        Index("ix_billing_audit_actor", "actor_id"),
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


__all__ = ["BillingAudit", "BillingReport", "BillingStatistic"]
