"""Deployment profiles, targets, inventory, jobs, history, versions,
artifacts, and the current per-target status board."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    DeploymentEngine,
    DeploymentJobStatus,
    DeploymentJobType,
    DeploymentStrategy,
    DeploymentTargetType,
    InstallationMode,
    InventoryNodeStatus,
)


class DeploymentProfile(BaseModel):
    """``deployment_profiles`` -- one named deployment configuration: a
    target type, installation mode, deployment engine, and strategy."""

    __tablename__ = "deployment_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_deployment_profile_name"),
    )

    name: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[DeploymentTargetType] = mapped_column(String(32), index=True)
    installation_mode: Mapped[InstallationMode] = mapped_column(String(24))
    engine: Mapped[DeploymentEngine] = mapped_column(String(24))
    strategy: Mapped[DeploymentStrategy] = mapped_column(String(24))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DeploymentTarget(BaseModel):
    """``deployment_targets`` -- one concrete environment a profile can
    deploy to (a cluster, a compose host, a cloud account)."""

    __tablename__ = "deployment_targets"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_deployment_target_name"),
        Index("ix_deployment_target_profile", "deployment_profile_id"),
    )

    deployment_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[DeploymentTargetType] = mapped_column(String(32), index=True)
    endpoint: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[InventoryNodeStatus] = mapped_column(
        String(16), default=InventoryNodeStatus.UNKNOWN, index=True
    )


class DeploymentInventory(BaseModel):
    """``deployment_inventory`` -- one node registered under a
    deployment target."""

    __tablename__ = "deployment_inventory"
    __table_args__ = (Index("ix_deployment_inventory_target", "deployment_target_id"),)

    deployment_target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_targets.id", ondelete="CASCADE"), index=True
    )
    node_name: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(64), default="worker")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[InventoryNodeStatus] = mapped_column(
        String(16), default=InventoryNodeStatus.UNKNOWN, index=True
    )


class DeploymentJob(BaseModel):
    """``deployment_jobs`` -- one install/deploy/upgrade/rollback run,
    shared lifecycle across every job type -- see
    ``app.deployment.engine`` for the transition table."""

    __tablename__ = "deployment_jobs"
    __table_args__ = (
        Index("ix_deployment_job_profile", "deployment_profile_id"),
        Index("ix_deployment_job_type", "job_type"),
        Index("ix_deployment_job_status", "status"),
    )

    deployment_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_profiles.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[DeploymentJobType] = mapped_column(String(16), index=True)
    status: Mapped[DeploymentJobStatus] = mapped_column(
        String(16), default=DeploymentJobStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")


class DeploymentHistory(BaseModel):
    """``deployment_history`` -- one append-only lifecycle event for a
    deployment job."""

    __tablename__ = "deployment_history"
    __table_args__ = (Index("ix_deployment_history_job", "deployment_job_id"),)

    deployment_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_jobs.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DeploymentVersion(BaseModel):
    """``deployment_versions`` -- one platform release known to this
    installation."""

    __tablename__ = "deployment_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "version_label", name="uq_deployment_version_label"),
    )

    version_label: Mapped[str] = mapped_column(String(32), index=True)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class DeploymentArtifact(BaseModel):
    """``deployment_artifacts`` -- one build artifact belonging to a
    platform release."""

    __tablename__ = "deployment_artifacts"
    __table_args__ = (Index("ix_deployment_artifact_version", "deployment_version_id"),)

    deployment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_versions.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    storage_ref: Mapped[str] = mapped_column(String(512), default="")


class DeploymentStatusRecord(BaseModel):
    """``deployment_status`` -- the current live status of a deployment
    on a given target; the status *board*, distinct from
    ``deployment_history``'s append-only event log."""

    __tablename__ = "deployment_status"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "deployment_target_id", name="uq_deployment_status_target"
        ),
    )

    deployment_target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployment_targets.id", ondelete="CASCADE"), index=True
    )
    deployment_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deployment_jobs.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[DeploymentJobStatus] = mapped_column(
        String(16), default=DeploymentJobStatus.PENDING, index=True
    )
    detail: Mapped[str] = mapped_column(Text, default="")
    updated_at_status: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """When *status* itself was last recomputed -- distinct from the
    row's own ``updated_at`` (which tracks any column change) so a
    reader can tell a genuine status recomputation from an unrelated
    field edit."""


__all__ = [
    "DeploymentArtifact",
    "DeploymentHistory",
    "DeploymentInventory",
    "DeploymentJob",
    "DeploymentProfile",
    "DeploymentStatusRecord",
    "DeploymentTarget",
    "DeploymentVersion",
]
