"""Ongoing operational and governance state: cost, budgets, policies,
compliance, drift, Infrastructure-as-Code tracking, and the service
catalog.

**Every time-series table here is an immutable row per event, never a
single mutable row a fresh check overwrites in place** -- matching
``services/multi-cluster-management-service``'s own operations tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    BudgetPeriod,
    CatalogItemStatus,
    CloudComplianceFramework,
    CloudComplianceStatus,
    CloudPolicyStatus,
    CloudPolicyType,
    CloudResourceType,
    DriftSeverity,
    DriftStatus,
    IaCDeploymentStatus,
    IaCTool,
)


class CloudCost(BaseModel):
    """``cloud_costs`` -- one cost line item for one account, optionally
    attributed to a specific resource, over one period."""

    __tablename__ = "cloud_costs"
    __table_args__ = (
        Index("ix_cloud_cost_account", "account_id"),
        Index("ix_cloud_cost_resource", "resource_id"),
        Index("ix_cloud_cost_period", "period_start"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="SET NULL"), default=None
    )
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    cost_category: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CloudBudget(BaseModel):
    """``cloud_budgets`` -- one budget definition, org-wide if
    ``account_id`` is ``None`` or scoped to a single account."""

    __tablename__ = "cloud_budgets"
    __table_args__ = (Index("ix_cloud_budget_account", "account_id"),)

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    period: Mapped[BudgetPeriod] = mapped_column(String(16), default=BudgetPeriod.MONTHLY)
    threshold_fraction: Mapped[float] = mapped_column(Float, default=0.8)
    current_spend: Mapped[float] = mapped_column(Float, default=0.0)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CloudPolicy(BaseModel):
    """``cloud_policies`` -- one governance policy (tag, naming, quota,
    budget, security, approval, or resource-restriction), org-wide if
    ``scope_account_id`` is ``None``."""

    __tablename__ = "cloud_policies"
    __table_args__ = (
        Index("ix_cloud_policy_type", "policy_type"),
        Index("ix_cloud_policy_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(255))
    policy_type: Mapped[CloudPolicyType] = mapped_column(String(24), index=True)
    definition: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[CloudPolicyStatus] = mapped_column(
        String(16), default=CloudPolicyStatus.DRAFT, index=True
    )
    scope_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="SET NULL"), default=None
    )


class CloudCompliance(BaseModel):
    """``cloud_compliance`` -- one framework assessment for one
    account."""

    __tablename__ = "cloud_compliance"
    __table_args__ = (
        Index("ix_cloud_compliance_account", "account_id"),
        Index("ix_cloud_compliance_framework", "framework"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True
    )
    framework: Mapped[CloudComplianceFramework] = mapped_column(String(16), index=True)
    status: Mapped[CloudComplianceStatus] = mapped_column(
        String(24), default=CloudComplianceStatus.NOT_ASSESSED
    )
    score: Mapped[float | None] = mapped_column(Float, default=None)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remediation_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class CloudDrift(BaseModel):
    """``cloud_drift`` -- one detected drift event for one resource."""

    __tablename__ = "cloud_drift"
    __table_args__ = (
        Index("ix_cloud_drift_resource", "resource_id"),
        Index("ix_cloud_drift_status", "status"),
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[DriftSeverity] = mapped_column(String(8), default=DriftSeverity.LOW)
    status: Mapped[DriftStatus] = mapped_column(
        String(16), default=DriftStatus.DETECTED, index=True
    )
    desired_state_hash: Mapped[str | None] = mapped_column(String(128), default=None)
    live_state_hash: Mapped[str | None] = mapped_column(String(128), default=None)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CloudIaC(BaseModel):
    """``cloud_iac`` -- one Infrastructure-as-Code deployment tracking
    row, optionally attributed to a specific resource."""

    __tablename__ = "cloud_iac"
    __table_args__ = (
        Index("ix_cloud_iac_resource", "resource_id"),
        Index("ix_cloud_iac_status", "status"),
    )

    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="SET NULL"), default=None
    )
    tool: Mapped[IaCTool] = mapped_column(String(24))
    status: Mapped[IaCDeploymentStatus] = mapped_column(
        String(16), default=IaCDeploymentStatus.PLANNED, index=True
    )
    state_reference: Mapped[str | None] = mapped_column(String(512), default=None)
    version_label: Mapped[str | None] = mapped_column(String(32), default=None)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CloudCatalogItem(BaseModel):
    """``cloud_catalog`` -- one service catalog template/blueprint."""

    __tablename__ = "cloud_catalog"
    __table_args__ = (Index("ix_cloud_catalog_status", "status"),)

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1024), default=None)
    resource_type: Mapped[CloudResourceType] = mapped_column(String(24), index=True)
    status: Mapped[CatalogItemStatus] = mapped_column(
        String(24), default=CatalogItemStatus.DRAFT, index=True
    )
    version_label: Mapped[str] = mapped_column(String(32))
    template: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = [
    "CloudBudget",
    "CloudCatalogItem",
    "CloudCompliance",
    "CloudCost",
    "CloudDrift",
    "CloudIaC",
    "CloudPolicy",
]
