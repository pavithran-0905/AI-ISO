"""Rolled-up SDK/CLI statistics, generated reports, and the immutable
audit trail.

The audit trail is append-only by convention and by absence: there is
no update path to it anywhere in this service, matching
``services/administration-portal-service``'s own ``SystemAudit``
precedent.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import AuditAction, ReportFormat, ReportKind, ReportStatus


class CliStatistic(BaseModel):
    """``cli_statistics`` -- one rolled-up window of combined SDK and
    CLI activity.

    Idempotent per window, matching every other AI-IOS statistics
    table: the worker updates the row for a window rather than
    inserting a second, so a retried rollup cannot double-count. Serves
    both ``GET /sdk/statistics`` and ``GET /cli/statistics`` -- docs/071
    names only this one statistics table, not a separate ``sdk_statistics``.
    """

    __tablename__ = "cli_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "window_start", name="uq_cli_statistic_window"),
        Index("ix_cli_statistic_window", "window_start"),
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    sdk_download_count: Mapped[int] = mapped_column(Integer, default=0)
    cli_download_count: Mapped[int] = mapped_column(Integer, default=0)
    command_execution_count: Mapped[int] = mapped_column(Integer, default=0)
    plugin_install_count: Mapped[int] = mapped_column(Integer, default=0)
    auth_success_count: Mapped[int] = mapped_column(Integer, default=0)
    auth_failure_count: Mapped[int] = mapped_column(Integer, default=0)


class CliReport(BaseModel):
    """``cli_reports`` -- one generated report, of any of the seven
    kinds docs/071's own REPORTING section names."""

    __tablename__ = "cli_reports"
    __table_args__ = (
        Index("ix_cli_report_kind", "kind"),
        Index("ix_cli_report_status", "status"),
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


class SdkAudit(BaseModel):
    """``sdk_audit`` -- the immutable trail.

    Every SDK release, CLI release, plugin management action,
    authentication event, and administrative operation is recorded
    here, per docs/071's own AUDIT section.
    """

    __tablename__ = "sdk_audit"
    __table_args__ = (
        Index("ix_sdk_audit_time", "occurred_at"),
        Index("ix_sdk_audit_action", "action"),
        Index("ix_sdk_audit_actor", "actor_id"),
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


__all__ = ["CliReport", "CliStatistic", "SdkAudit"]
