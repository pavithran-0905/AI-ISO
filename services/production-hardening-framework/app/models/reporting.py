"""Rollup statistics, generated reports, and the immutable audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import HardeningAuditAction, HardeningReportKind, ReportFormat, ReportStatus


class HardeningStatistic(BaseModel):
    """``hardening_statistics`` -- one rolled-up activity window."""

    __tablename__ = "hardening_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "window_start", name="uq_hardening_statistic_window"),
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hardening_run_count: Mapped[int] = mapped_column(Integer, default=0)
    security_finding_count: Mapped[int] = mapped_column(Integer, default=0)
    vulnerability_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_hardening_score: Mapped[float] = mapped_column(Float, default=0.0)


class HardeningReport(BaseModel):
    """``hardening_reports`` -- one generated report."""

    __tablename__ = "hardening_reports"
    __table_args__ = (
        Index("ix_hardening_report_kind", "kind"),
        Index("ix_hardening_report_status", "status"),
    )

    kind: Mapped[HardeningReportKind] = mapped_column(String(24), index=True)
    report_format: Mapped[ReportFormat] = mapped_column(String(8), default=ReportFormat.JSON)
    title: Mapped[str] = mapped_column(String(256))
    status: Mapped[ReportStatus] = mapped_column(
        String(16), default=ReportStatus.PENDING, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    row_count: Mapped[int] = mapped_column(Integer, default=0)


class HardeningAudit(BaseModel):
    """``hardening_audit`` -- the immutable audit trail: hardening
    runs, security changes, certification decisions, compliance
    validation, and administrative actions."""

    __tablename__ = "hardening_audit"
    __table_args__ = (
        Index("ix_hardening_audit_action", "action"),
        Index("ix_hardening_audit_entity", "entity_type", "entity_id"),
        Index("ix_hardening_audit_occurred_at", "occurred_at"),
    )

    action: Mapped[HardeningAuditAction] = mapped_column(String(24), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None)
    summary: Mapped[str] = mapped_column(String(1024))
    detail: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["HardeningAudit", "HardeningReport", "HardeningStatistic"]
