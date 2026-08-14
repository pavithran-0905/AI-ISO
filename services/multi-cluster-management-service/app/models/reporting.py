"""Workload placement, the cluster event timeline, rolled-up statistics,
generated reports, and the immutable fleet audit trail.

The audit trail is append-only by convention and by absence: there is no
update path to it anywhere in this service, matching
``services/backup-dr-service``'s ``BackupAudit`` precedent exactly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    AuditAction,
    DeploymentStrategy,
    ReportFormat,
    ReportKind,
    ReportStatus,
    WorkloadPlacementStatus,
)


class ClusterWorkload(BaseModel):
    """``cluster_workloads`` -- one application's placement onto one
    cluster, with the strategy and rules that governed the placement
    decision.

    ``cluster_id`` is nullable: a placement request that found no
    eligible cluster is still recorded, with ``placement_status ==
    FAILED`` and no cluster to reference -- there is nothing to point at,
    not a foreign key this service forgot to set.
    """

    __tablename__ = "cluster_workloads"
    __table_args__ = (
        Index("ix_cluster_workload_cluster", "cluster_id"),
        Index("ix_cluster_workload_status", "placement_status"),
    )

    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), default=None, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    namespace: Mapped[str | None] = mapped_column(String(255), default=None)
    deployment_strategy: Mapped[DeploymentStrategy] = mapped_column(
        String(16), default=DeploymentStrategy.ROLLING_UPDATE
    )
    placement_status: Mapped[WorkloadPlacementStatus] = mapped_column(
        String(16), default=WorkloadPlacementStatus.PENDING, index=True
    )
    replicas: Mapped[int | None] = mapped_column(Integer, default=None)
    affinity_rules: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ClusterEvent(BaseModel):
    """``cluster_events`` -- the per-cluster timeline (lifecycle
    transitions, health changes, policy applications, ...), distinct
    from both the RabbitMQ-published domain events
    (:mod:`app.events.domain_events`) and the immutable audit trail
    (:class:`ClusterAudit`) below -- this is what a fleet dashboard
    renders as "recent activity" for one cluster."""

    __tablename__ = "cluster_events"
    __table_args__ = (
        Index("ix_cluster_event_cluster", "cluster_id"),
        Index("ix_cluster_event_kind", "event_kind"),
        Index("ix_cluster_event_occurred", "occurred_at"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clusters.id", ondelete="CASCADE"), index=True
    )
    event_kind: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class ClusterStatistic(BaseModel):
    """``cluster_statistics`` -- one rolled-up fleet-wide window.

    Idempotent per window, matching every other AI-IOS statistics table:
    the worker updates the row for a window rather than inserting a
    second, so a retried rollup cannot double-count.
    """

    __tablename__ = "cluster_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "window_start", name="uq_cluster_statistic_window"),
        Index("ix_cluster_statistic_window", "window_start"),
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    clusters_registered: Mapped[int] = mapped_column(Integer, default=0)
    clusters_healthy: Mapped[int] = mapped_column(Integer, default=0)
    clusters_degraded: Mapped[int] = mapped_column(Integer, default=0)
    clusters_unhealthy: Mapped[int] = mapped_column(Integer, default=0)

    policy_violations: Mapped[int] = mapped_column(Integer, default=0)
    compliance_violations: Mapped[int] = mapped_column(Integer, default=0)

    upgrades_completed: Mapped[int] = mapped_column(Integer, default=0)
    upgrades_failed: Mapped[int] = mapped_column(Integer, default=0)

    total_node_count: Mapped[int] = mapped_column(BigInteger, default=0)


class ClusterReport(BaseModel):
    """``cluster_reports`` -- one generated report."""

    __tablename__ = "cluster_reports"
    __table_args__ = (
        Index("ix_cluster_report_kind", "kind"),
        Index("ix_cluster_report_status", "status"),
    )

    kind: Mapped[ReportKind] = mapped_column(String(24), index=True)
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
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class ClusterAudit(BaseModel):
    """``cluster_audit`` -- the immutable trail.

    Every cluster registration, credential change, policy update,
    upgrade operation, compliance change, and administrative operation is
    recorded here, per docs/066's own AUDIT section.
    """

    __tablename__ = "cluster_audit"
    __table_args__ = (
        Index("ix_cluster_audit_time", "occurred_at"),
        Index("ix_cluster_audit_action", "action"),
        Index("ix_cluster_audit_actor", "actor_id"),
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


__all__ = [
    "ClusterAudit",
    "ClusterEvent",
    "ClusterReport",
    "ClusterStatistic",
    "ClusterWorkload",
]
