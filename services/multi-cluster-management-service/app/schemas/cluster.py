"""Request/response schemas for the 15 docs/066 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CapacityResourceKind,
    ClusterComplianceStatus,
    ClusterHealthStatus,
    ClusterLifecycleState,
    ClusterType,
    ComplianceFramework,
    DeploymentStrategy,
    ReportFormat,
    ReportKind,
    ReportStatus,
    UpgradeStatus,
    UpgradeStrategy,
    WorkloadPlacementStatus,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class PageInfo(_Base):
    has_more: bool = False


# ---- clusters -----------------------------------------------------------------------------


class ClusterCreateRequest(_Base):
    name: str
    cluster_type: ClusterType
    environment: str = "production"
    group_id: UUID | None = None
    region_id: UUID | None = None


class ClusterUpdateRequest(_Base):
    group_id: UUID | None = None
    region_id: UUID | None = None
    environment: str | None = None
    description: str | None = None
    labels: dict[str, str] | None = None
    tags: list[str] | None = None


class ClusterResponse(_Base):
    id: UUID
    name: str
    cluster_type: ClusterType
    lifecycle_state: ClusterLifecycleState
    environment: str
    group_id: UUID | None
    region_id: UUID | None
    api_endpoint: str | None
    kubernetes_version: str | None
    node_count: int | None
    health_status: ClusterHealthStatus
    is_schedulable: bool
    registered_at: datetime | None
    last_seen_at: datetime | None


class ClustersResponse(_Base):
    clusters: list[ClusterResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


class ClusterValidationResponse(_Base):
    cluster_id: UUID
    is_valid: bool
    detail: str


class DrainResponse(_Base):
    cluster_id: UUID
    workloads_marked: int


# ---- upgrades -----------------------------------------------------------------------------


class UpgradeRequest(_Base):
    to_version: str
    strategy: UpgradeStrategy = UpgradeStrategy.ROLLING


class UpgradeResponse(_Base):
    upgrade_id: UUID | None
    cluster_id: UUID
    to_version: str
    status: UpgradeStatus | None
    refusal: str | None
    detail: str


# ---- health / capacity / compliance --------------------------------------------------------


class ClusterHealthResponse(_Base):
    cluster_id: UUID
    health_status: ClusterHealthStatus
    last_health_check_at: datetime | None


class FleetHealthResponse(_Base):
    clusters: list[ClusterHealthResponse]
    total: int


class ClusterCapacityResponse(_Base):
    cluster_id: UUID
    resource_kind: CapacityResourceKind
    total: float
    used: float
    utilization_fraction: float | None
    measured_at: datetime


class FleetCapacityResponse(_Base):
    readings: list[ClusterCapacityResponse]
    total: int


class ClusterComplianceResponse(_Base):
    cluster_id: UUID
    framework: ComplianceFramework
    status: ClusterComplianceStatus
    score: float | None
    assessed_at: datetime


class FleetComplianceResponse(_Base):
    assessments: list[ClusterComplianceResponse]
    total: int


# ---- statistics / reports -------------------------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    clusters_registered: int
    clusters_healthy: int
    clusters_degraded: int
    clusters_unhealthy: int
    policy_violations: int
    compliance_violations: int
    upgrades_completed: int
    upgrades_failed: int


class StatisticsResponse(_Base):
    windows: list[StatisticWindowResponse]
    total: int


class ReportResponse(_Base):
    id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: ReportStatus
    period_start: datetime | None
    period_end: datetime | None
    generated_at: datetime | None
    row_count: int | None


class ReportsResponse(_Base):
    reports: list[ReportResponse]
    total: int


# ---- workload placement (used by /clusters/{id}/drain and future placement routes) ---------


class WorkloadPlacementResponse(_Base):
    id: UUID
    cluster_id: UUID | None
    name: str
    namespace: str | None
    deployment_strategy: DeploymentStrategy
    placement_status: WorkloadPlacementStatus


__all__ = [
    "MAX_PAGE_SIZE",
    "ClusterCapacityResponse",
    "ClusterComplianceResponse",
    "ClusterCreateRequest",
    "ClusterHealthResponse",
    "ClusterResponse",
    "ClusterUpdateRequest",
    "ClusterValidationResponse",
    "ClustersResponse",
    "DrainResponse",
    "FleetCapacityResponse",
    "FleetComplianceResponse",
    "FleetHealthResponse",
    "PageInfo",
    "ReportResponse",
    "ReportsResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "UpgradeRequest",
    "UpgradeResponse",
    "WorkloadPlacementResponse",
]
