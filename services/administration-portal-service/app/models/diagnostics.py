"""System diagnostics runs and component health checks."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DiagnosticCategory, HealthCheckStatus


class Diagnostic(BaseModel):
    """``diagnostics`` -- one diagnostic run for one platform
    dependency category."""

    __tablename__ = "diagnostics"
    __table_args__ = (
        Index("ix_diagnostic_category", "category"),
        Index("ix_diagnostic_ran_at", "ran_at"),
    )

    category: Mapped[DiagnosticCategory] = mapped_column(String(16), index=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[HealthCheckStatus] = mapped_column(
        String(16), default=HealthCheckStatus.UNKNOWN, index=True
    )
    latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


class HealthCheck(BaseModel):
    """``health_checks`` -- one component's latest health reading."""

    __tablename__ = "health_checks"
    __table_args__ = (
        Index("ix_health_check_component", "component"),
        Index("ix_health_check_status", "status"),
    )

    component: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[HealthCheckStatus] = mapped_column(
        String(16), default=HealthCheckStatus.UNKNOWN, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


__all__ = ["Diagnostic", "HealthCheck"]
