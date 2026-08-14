"""Background system jobs and their per-transition history."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import JobPriority, JobStatus


class SystemJob(BaseModel):
    """``system_jobs`` -- one background job, at any point in its
    execution lifecycle."""

    __tablename__ = "system_jobs"
    __table_args__ = (
        Index("ix_system_job_status", "status"),
        Index("ix_system_job_priority", "priority"),
    )

    job_key: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[JobStatus] = mapped_column(String(16), default=JobStatus.QUEUED, index=True)
    priority: Mapped[JobPriority] = mapped_column(String(8), default=JobPriority.NORMAL, index=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(1024), default=None)


class JobHistory(BaseModel):
    """``job_history`` -- one immutable transition record for a job."""

    __tablename__ = "job_history"
    __table_args__ = (Index("ix_job_history_job", "job_id"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("system_jobs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[JobStatus] = mapped_column(String(16), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


__all__ = ["JobHistory", "SystemJob"]
