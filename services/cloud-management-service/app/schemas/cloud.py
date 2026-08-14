"""Request/response schemas for the 15 docs/068 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    BudgetPeriod,
    CloudComplianceFramework,
    CloudComplianceStatus,
    CloudProviderType,
    CloudResourceLifecycleState,
    CloudResourceType,
    ReportFormat,
    ReportKind,
    ReportStatus,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class PageInfo(_Base):
    has_more: bool = False


# ---- providers ----------------------------------------------------------------------------


class ProviderResponse(_Base):
    id: UUID
    provider_type: CloudProviderType
    name: str
    is_enabled: bool


class ProvidersResponse(_Base):
    providers: list[ProviderResponse]
    total: int


# ---- accounts -----------------------------------------------------------------------------


class AccountCreateRequest(_Base):
    provider_id: UUID
    external_account_id: str
    name: str
    credential_ref: str
    credential_expires_at: datetime | None = None


class AccountResponse(_Base):
    id: UUID
    provider_id: UUID
    external_account_id: str
    name: str
    is_valid: bool
    health_status: str
    last_validated_at: datetime | None
    registered_at: datetime | None


class AccountsResponse(_Base):
    accounts: list[AccountResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- resources ----------------------------------------------------------------------------


class ResourceDiscoverRequest(_Base):
    account_id: UUID
    resource_type: CloudResourceType
    external_id: str
    name: str
    cloud_project_id: UUID | None = None
    region_id: UUID | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ResourceProvisionRequest(_Base):
    resource_id: UUID
    target_state: CloudResourceLifecycleState = CloudResourceLifecycleState.PROVISIONING


class ResourceUpdateRequest(_Base):
    name: str | None = None
    tags: dict[str, str] | None = None
    labels: dict[str, str] | None = None


class ResourceResponse(_Base):
    id: UUID
    account_id: UUID
    cloud_project_id: UUID | None
    region_id: UUID | None
    resource_type: CloudResourceType
    external_id: str
    name: str
    lifecycle_state: CloudResourceLifecycleState
    tags: dict[str, str]
    discovered_at: datetime | None
    last_synced_at: datetime | None
    provisioned_at: datetime | None


class ResourcesResponse(_Base):
    resources: list[ResourceResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- cost / budgets -------------------------------------------------------------------------


class CostItemResponse(_Base):
    id: UUID
    account_id: UUID
    resource_id: UUID | None
    amount: float
    currency: str
    cost_category: str
    period_start: datetime
    period_end: datetime


class CostResponse(_Base):
    items: list[CostItemResponse]
    total_amount: float
    total: int


class BudgetCreateRequest(_Base):
    account_id: UUID | None = None
    name: str
    amount: float
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    threshold_fraction: float = 0.8
    period_start: datetime
    period_end: datetime


class BudgetResponse(_Base):
    id: UUID
    account_id: UUID | None
    name: str
    amount: float
    period: BudgetPeriod
    threshold_fraction: float
    current_spend: float
    period_start: datetime
    period_end: datetime


class BudgetsResponse(_Base):
    budgets: list[BudgetResponse]
    total: int


# ---- optimization ---------------------------------------------------------------------------


class OptimizationRecommendation(_Base):
    resource_id: UUID
    is_idle: bool
    recommendation: str


class OptimizationResponse(_Base):
    recommendations: list[OptimizationRecommendation]
    total: int


# ---- compliance -----------------------------------------------------------------------------


class ComplianceAssessmentResponse(_Base):
    account_id: UUID
    framework: CloudComplianceFramework
    status: CloudComplianceStatus
    score: float | None
    assessed_at: datetime


class ComplianceResponse(_Base):
    assessments: list[ComplianceAssessmentResponse]
    total: int


# ---- statistics / reports -------------------------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    resources_discovered: int
    resources_provisioned: int
    total_cost: float
    budgets_exceeded: int
    drift_detected_count: int
    compliance_violations: int


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


__all__ = [
    "MAX_PAGE_SIZE",
    "AccountCreateRequest",
    "AccountResponse",
    "AccountsResponse",
    "BudgetCreateRequest",
    "BudgetResponse",
    "BudgetsResponse",
    "ComplianceAssessmentResponse",
    "ComplianceResponse",
    "CostItemResponse",
    "CostResponse",
    "OptimizationRecommendation",
    "OptimizationResponse",
    "PageInfo",
    "ProviderResponse",
    "ProvidersResponse",
    "ReportResponse",
    "ReportsResponse",
    "ResourceDiscoverRequest",
    "ResourceProvisionRequest",
    "ResourceResponse",
    "ResourceUpdateRequest",
    "ResourcesResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
]
