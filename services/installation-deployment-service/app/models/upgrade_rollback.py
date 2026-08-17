"""Upgrade and rollback history, each tied to the deployment job that
carried it out."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DeploymentJobStatus


class UpgradeHistory(BaseModel):
    """``upgrade_history`` -- one platform upgrade attempt."""

    __tablename__ = "upgrade_history"
    __table_args__ = (Index("ix_upgrade_history_job", "deployment_job_id"),)

    deployment_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_jobs.id", ondelete="CASCADE"), index=True
    )
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[DeploymentJobStatus] = mapped_column(
        String(16), default=DeploymentJobStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class RollbackHistory(BaseModel):
    """``rollback_history`` -- one platform rollback attempt."""

    __tablename__ = "rollback_history"
    __table_args__ = (Index("ix_rollback_history_job", "deployment_job_id"),)

    deployment_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_jobs.id", ondelete="CASCADE"), index=True
    )
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[DeploymentJobStatus] = mapped_column(
        String(16), default=DeploymentJobStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["RollbackHistory", "UpgradeHistory"]
