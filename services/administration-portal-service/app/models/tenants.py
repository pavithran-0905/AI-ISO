"""Organizations, tenants, and every per-tenant administrative record.

**``Tenant.organization_ref_id`` is a real foreign key** -- unlike a
cross-service reference, ``Organization`` lives in this same service's
own database, so Postgres can and does enforce it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import HealthCheckStatus, OrganizationStatus, ProvisioningStatus, TenantStatus


class Organization(BaseModel):
    """``organizations`` -- one administered business entity."""

    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organization_status", "status"),)

    name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[OrganizationStatus] = mapped_column(
        String(16), default=OrganizationStatus.ACTIVE, index=True
    )
    external_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    """A correlation id for this organization's own row in
    ``services/organization-service`` (Prompt 033) -- never a foreign
    key, since that table lives in a different service's database."""


class Tenant(BaseModel):
    """``tenants`` -- one provisioned tenant under an organization."""

    __tablename__ = "tenants"
    __table_args__ = (
        Index("ix_tenant_organization_ref", "organization_ref_id"),
        Index("ix_tenant_status", "status"),
    )

    organization_ref_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[TenantStatus] = mapped_column(
        String(16), default=TenantStatus.PROVISIONING, index=True
    )
    isolation_key: Mapped[str | None] = mapped_column(String(255), default=None)
    """The schema/namespace/partition key proving this tenant's data is
    isolated -- ``None`` until provisioning assigns one."""


class TenantSetting(BaseModel):
    """``tenant_settings`` -- one per-tenant configuration override."""

    __tablename__ = "tenant_settings"
    __table_args__ = (Index("ix_tenant_setting_tenant", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class TenantLimit(BaseModel):
    """``tenant_limits`` -- one static resource ceiling for a tenant."""

    __tablename__ = "tenant_limits"
    __table_args__ = (Index("ix_tenant_limit_tenant", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    metric_key: Mapped[str] = mapped_column(String(128), index=True)
    limit_value: Mapped[float] = mapped_column(Float)


class TenantUsage(BaseModel):
    """``tenant_usage`` -- one recorded usage reading for a tenant."""

    __tablename__ = "tenant_usage"
    __table_args__ = (Index("ix_tenant_usage_tenant", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    metric_key: Mapped[str] = mapped_column(String(128), index=True)
    used_value: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TenantHealth(BaseModel):
    """``tenant_health`` -- one tenant health reading."""

    __tablename__ = "tenant_health"
    __table_args__ = (Index("ix_tenant_health_tenant", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[HealthCheckStatus] = mapped_column(
        String(16), default=HealthCheckStatus.UNKNOWN, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


class TenantProvisioning(BaseModel):
    """``tenant_provisioning`` -- one provisioning/migration/backup/
    restore operation record for a tenant."""

    __tablename__ = "tenant_provisioning"
    __table_args__ = (Index("ix_tenant_provisioning_tenant", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ProvisioningStatus] = mapped_column(
        String(16), default=ProvisioningStatus.PENDING, index=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)


__all__ = [
    "Organization",
    "Tenant",
    "TenantHealth",
    "TenantLimit",
    "TenantProvisioning",
    "TenantSetting",
    "TenantUsage",
]
