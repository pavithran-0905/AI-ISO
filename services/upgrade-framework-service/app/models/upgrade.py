"""Upgrade plans, jobs, history, per-target fleet tracking, and
declared dependencies."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    CheckResultStatus,
    UpgradeJobStatus,
    UpgradeStrategy,
    UpgradeTargetStatus,
    UpgradeTargetType,
)


class UpgradePlan(BaseModel):
    """``upgrade_plans`` -- one named, reusable upgrade definition: a
    target type, strategy, and version range."""

    __tablename__ = "upgrade_plans"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_upgrade_plan_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[UpgradeTargetType] = mapped_column(String(24), index=True)
    strategy: Mapped[UpgradeStrategy] = mapped_column(String(24))
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    release_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("release_channels.id", ondelete="SET NULL"), default=None
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class UpgradeJob(BaseModel):
    """``upgrade_jobs`` -- one execution of an upgrade plan -- see
    ``app.upgrade.engine`` for the transition table this drives."""

    __tablename__ = "upgrade_jobs"
    __table_args__ = (
        Index("ix_upgrade_job_plan", "upgrade_plan_id"),
        Index("ix_upgrade_job_status", "status"),
    )

    upgrade_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_plans.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[UpgradeJobStatus] = mapped_column(
        String(16), default=UpgradeJobStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")


class UpgradeHistory(BaseModel):
    """``upgrade_history`` -- one append-only lifecycle event for an
    upgrade job."""

    __tablename__ = "upgrade_history"
    __table_args__ = (Index("ix_upgrade_history_job", "upgrade_job_id"),)

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UpgradeTarget(BaseModel):
    """``upgrade_targets`` -- one concrete thing (a service, an edge
    device, a cluster) being upgraded within a fleet upgrade job."""

    __tablename__ = "upgrade_targets"
    __table_args__ = (Index("ix_upgrade_target_job", "upgrade_job_id"),)

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    target_ref: Mapped[str] = mapped_column(String(256))
    target_type: Mapped[UpgradeTargetType] = mapped_column(String(24), index=True)
    status: Mapped[UpgradeTargetStatus] = mapped_column(
        String(16), default=UpgradeTargetStatus.PENDING, index=True
    )
    wave_number: Mapped[int] = mapped_column(default=0)


class UpgradeResult(BaseModel):
    """``upgrade_results`` -- the final outcome recorded for one
    upgrade target."""

    __tablename__ = "upgrade_results"
    __table_args__ = (Index("ix_upgrade_result_target", "upgrade_target_id"),)

    upgrade_target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_targets.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[UpgradeTargetStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UpgradeDependency(BaseModel):
    """``upgrade_dependencies`` -- one dependency an upgrade plan
    declares a version requirement against."""

    __tablename__ = "upgrade_dependencies"
    __table_args__ = (Index("ix_upgrade_dependency_plan", "upgrade_plan_id"),)

    upgrade_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_plans.id", ondelete="CASCADE"), index=True
    )
    dependency_name: Mapped[str] = mapped_column(String(128), index=True)
    required_version: Mapped[str] = mapped_column(String(32))
    found_version: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)


__all__ = [
    "UpgradeDependency",
    "UpgradeHistory",
    "UpgradeJob",
    "UpgradePlan",
    "UpgradeResult",
    "UpgradeTarget",
]
