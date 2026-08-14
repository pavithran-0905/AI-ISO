"""Core fleet identity: clusters, their grouping/regions, credentials,
and the version catalog upgrade planning checks against.

**A cluster's credential is a lookup key into secrets-management-service,
never a raw kubeconfig or token stored here.** This service orchestrates
fleet operations; it does not become a second place a cluster-admin
credential can leak from -- the exact same posture
``services/backup-dr-service`` takes with ``BackupTarget.connection_ref``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    ClusterHealthStatus,
    ClusterLifecycleState,
    ClusterType,
    RegistrationMethod,
)


class ClusterRegion(BaseModel):
    """``cluster_regions`` -- a named region/provider a cluster can be
    placed in, with its availability zones."""

    __tablename__ = "cluster_regions"
    __table_args__ = (Index("ix_cluster_region_code", "code"),)

    name: Mapped[str] = mapped_column(String(255), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str | None] = mapped_column(String(64), default=None)
    availability_zones: Mapped[list[str]] = mapped_column(JSON, default=list)


class ClusterGroup(BaseModel):
    """``cluster_groups`` -- a named fleet segment (environment,
    business unit, or arbitrary grouping) policies and reports can target
    as a unit instead of one cluster at a time."""

    __tablename__ = "cluster_groups"
    __table_args__ = (Index("ix_cluster_group_name", "name"),)

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    business_unit: Mapped[str | None] = mapped_column(String(255), default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class Cluster(BaseModel):
    """``clusters`` -- one Kubernetes-conformant cluster this service
    knows about, anywhere in its lifecycle from discovery to archive."""

    __tablename__ = "clusters"
    __table_args__ = (
        Index("ix_cluster_type", "cluster_type"),
        Index("ix_cluster_lifecycle_state", "lifecycle_state"),
        Index("ix_cluster_health_status", "health_status"),
        Index("ix_cluster_group", "group_id"),
        Index("ix_cluster_region", "region_id"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    cluster_type: Mapped[ClusterType] = mapped_column(String(32), index=True)
    lifecycle_state: Mapped[ClusterLifecycleState] = mapped_column(
        String(24), default=ClusterLifecycleState.DISCOVERED, index=True
    )
    environment: Mapped[str] = mapped_column(String(64), default="production")
    project: Mapped[str | None] = mapped_column(String(255), default=None)

    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cluster_groups.id", ondelete="SET NULL"), default=None, index=True
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cluster_regions.id", ondelete="SET NULL"), default=None, index=True
    )

    api_endpoint: Mapped[str | None] = mapped_column(String(512), default=None)
    kubernetes_version: Mapped[str | None] = mapped_column(String(32), default=None)
    node_count: Mapped[int | None] = mapped_column(Integer, default=None)

    health_status: Mapped[ClusterHealthStatus] = mapped_column(
        String(16), default=ClusterHealthStatus.UNKNOWN, index=True
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    is_schedulable: Mapped[bool] = mapped_column(Boolean, default=True)
    """Whether new workloads may be placed on this cluster. Toggled by
    ``POST /clusters/{id}/cordon`` and ``.../uncordon`` -- distinct from
    ``lifecycle_state``, since a cluster can be temporarily cordoned
    without leaving ``ACTIVE`` (a scheduled maintenance window on one
    cluster in a group should not make the whole group look
    unavailable)."""

    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text, default=None)


class ClusterCredential(BaseModel):
    """``cluster_credentials`` -- how this service authenticates to one
    cluster, referenced by lookup key only (see module docstring)."""

    __tablename__ = "cluster_credentials"
    __table_args__ = (Index("ix_cluster_credential_cluster", "cluster_id"),)

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[RegistrationMethod] = mapped_column(String(24))
    credential_ref: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)


class ClusterVersion(BaseModel):
    """``cluster_versions`` -- the version catalog upgrade planning and
    compatibility checks are validated against, per distribution."""

    __tablename__ = "cluster_versions"
    __table_args__ = (Index("ix_cluster_version_type", "cluster_type"),)

    cluster_type: Mapped[ClusterType] = mapped_column(String(32), index=True)
    version_label: Mapped[str] = mapped_column(String(32))
    """The distribution's own version string (e.g. ``"1.29.4"``) --
    named to avoid colliding with ``BaseEntityMixin.version``, the
    optimistic-locking counter every AI-IOS entity already carries."""
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    end_of_life_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    skew_rank: Mapped[int] = mapped_column(Integer, default=0)
    """A monotonically increasing ordinal for this ``cluster_type``'s
    versions (0 = oldest known), used to compute version skew for the
    "at most N minor versions apart" upgrade-compatibility rule without
    parsing semver strings whose format differs across distributions."""


__all__ = [
    "Cluster",
    "ClusterCredential",
    "ClusterGroup",
    "ClusterRegion",
    "ClusterVersion",
]
