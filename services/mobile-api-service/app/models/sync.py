"""Synchronization jobs and the offline action queue."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import SyncJobStatus, SyncQueueStatus, SyncType


class MobileSyncJob(BaseModel):
    """``mobile_sync_jobs`` -- one synchronization run for one device."""

    __tablename__ = "mobile_sync_jobs"
    __table_args__ = (
        Index("ix_mobile_sync_job_device", "device_id"),
        Index("ix_mobile_sync_job_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    sync_type: Mapped[SyncType] = mapped_column(String(16), index=True)
    status: Mapped[SyncJobStatus] = mapped_column(
        String(16), default=SyncJobStatus.PENDING, index=True
    )
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    applied_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class MobileSyncQueueItem(BaseModel):
    """``mobile_sync_queue`` -- one queued offline action awaiting
    application to the server's own state."""

    __tablename__ = "mobile_sync_queue"
    __table_args__ = (
        Index("ix_mobile_sync_queue_job", "sync_job_id"),
        Index("ix_mobile_sync_queue_status", "status"),
    )

    sync_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_sync_jobs.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[SyncQueueStatus] = mapped_column(
        String(16), default=SyncQueueStatus.QUEUED, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_detail: Mapped[str | None] = mapped_column(String(512), default=None)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["MobileSyncJob", "MobileSyncQueueItem"]
