"""Ongoing operational state per cluster: inventory, health, capacity,
upgrades, compliance, and policy propagation.

**Every table here is a time series of readings, never a single mutable
row a fresh check overwrites in place.** A cluster's health five minutes
ago and its health now are different facts; collapsing them into one row
per cluster would make "when did this start degrading" unanswerable.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    CapacityResourceKind,
    ClusterComplianceStatus,
    ClusterComponent,
    ComplianceFramework,
    ComponentHealthStatus,
    PolicyPropagationStatus,
    PolicyType,
    UpgradeStatus,
    UpgradeStrategy,
)


class ClusterInventory(BaseModel):
    """``cluster_inventory`` -- one resource-kind count snapshot for one
    cluster (nodes, namespaces, deployments, ...), collected periodically."""

    __tablename__ = "cluster_inventory"
    __table_args__ = (
        Index("ix_cluster_inventory_cluster", "cluster_id"),
        Index("ix_cluster_inventory_kind", "resource_kind"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    resource_kind: Mapped[str] = mapped_column(String(64), index=True)
    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class ClusterHealth(BaseModel):
    """``cluster_health`` -- one component's health reading at one
    instant. :mod:`app.health.engine` rolls a cluster's most recent
    reading per component up into its overall
    :class:`~app.models.enums.ClusterHealthStatus`."""

    __tablename__ = "cluster_health"
    __table_args__ = (
        Index("ix_cluster_health_cluster", "cluster_id"),
        Index("ix_cluster_health_component", "component"),
        Index("ix_cluster_health_checked_at", "checked_at"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    component: Mapped[ClusterComponent] = mapped_column(String(24), index=True)
    status: Mapped[ComponentHealthStatus] = mapped_column(
        String(16), default=ComponentHealthStatus.UNKNOWN
    )
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ClusterCapacity(BaseModel):
    """``cluster_capacity`` -- one resource-kind capacity reading at one
    instant, feeding :mod:`app.capacity.engine`'s utilization and growth
    calculations."""

    __tablename__ = "cluster_capacity"
    __table_args__ = (
        Index("ix_cluster_capacity_cluster", "cluster_id"),
        Index("ix_cluster_capacity_kind", "resource_kind"),
        Index("ix_cluster_capacity_measured_at", "measured_at"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    resource_kind: Mapped[CapacityResourceKind] = mapped_column(String(16), index=True)
    total: Mapped[float] = mapped_column(Float)
    used: Mapped[float] = mapped_column(Float)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ClusterUpgrade(BaseModel):
    """``cluster_upgrades`` -- one upgrade execution for one cluster."""

    __tablename__ = "cluster_upgrades"
    __table_args__ = (
        Index("ix_cluster_upgrade_cluster", "cluster_id"),
        Index("ix_cluster_upgrade_status", "status"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    strategy: Mapped[UpgradeStrategy] = mapped_column(String(16), default=UpgradeStrategy.ROLLING)
    status: Mapped[UpgradeStatus] = mapped_column(
        String(16), default=UpgradeStatus.PLANNED, index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)

    pre_validation_passed: Mapped[bool | None] = mapped_column(Boolean, default=None)
    post_validation_passed: Mapped[bool | None] = mapped_column(Boolean, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class ClusterCompliance(BaseModel):
    """``cluster_compliance`` -- one cluster's standing against one
    framework, as of one assessment."""

    __tablename__ = "cluster_compliance"
    __table_args__ = (
        Index("ix_cluster_compliance_cluster", "cluster_id"),
        Index("ix_cluster_compliance_framework", "framework"),
        Index("ix_cluster_compliance_status", "status"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    framework: Mapped[ComplianceFramework] = mapped_column(String(24), index=True)
    status: Mapped[ClusterComplianceStatus] = mapped_column(
        String(24), default=ClusterComplianceStatus.NOT_ASSESSED, index=True
    )
    score: Mapped[float | None] = mapped_column(Float, default=None)
    findings: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remediation_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class ClusterPolicy(BaseModel):
    """``cluster_policies`` -- one policy, targeting either a single
    cluster or a whole :class:`~app.models.fleet.ClusterGroup`, and its
    propagation state."""

    __tablename__ = "cluster_policies"
    __table_args__ = (
        Index("ix_cluster_policy_cluster", "cluster_id"),
        Index("ix_cluster_policy_group", "group_id"),
        Index("ix_cluster_policy_type", "policy_type"),
        Index("ix_cluster_policy_status", "propagation_status"),
    )

    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), default=None, index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cluster_groups.id", ondelete="CASCADE"), default=None, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    policy_type: Mapped[PolicyType] = mapped_column(String(24), index=True)
    definition: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    propagation_status: Mapped[PolicyPropagationStatus] = mapped_column(
        String(16), default=PolicyPropagationStatus.PENDING, index=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = [
    "ClusterCapacity",
    "ClusterCompliance",
    "ClusterHealth",
    "ClusterInventory",
    "ClusterPolicy",
    "ClusterUpgrade",
]
