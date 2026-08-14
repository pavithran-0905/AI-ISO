"""Provider registration, cloud accounts, regions, and provider-side
projects (GCP projects / Azure resource groups / AWS OUs).

**A ``CloudAccount.credential_ref`` is a lookup key, never the secret
itself** -- matching ``services/multi-cluster-management-service``'s own
``ClusterCredential.credential_ref`` posture; the actual credential
material is secrets-management-service's job.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import AccountHealthStatus, CloudProviderType


class CloudProvider(BaseModel):
    """``cloud_providers`` -- one cloud provider integration enabled for
    an organization (e.g. "our AWS integration"), distinct from any
    specific account within it."""

    __tablename__ = "cloud_providers"
    __table_args__ = (Index("ix_cloud_provider_type", "provider_type"),)

    provider_type: Mapped[CloudProviderType] = mapped_column(String(24), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    """Non-secret provider configuration only (e.g. a default region) --
    never credential material."""


class CloudAccount(BaseModel):
    """``cloud_accounts`` -- one account/subscription/tenant registered
    within a provider."""

    __tablename__ = "cloud_accounts"
    __table_args__ = (
        Index("ix_cloud_account_provider", "provider_id"),
        Index("ix_cloud_account_health_status", "health_status"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_providers.id", ondelete="CASCADE"), index=True
    )
    external_account_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    credential_ref: Mapped[str] = mapped_column(String(512))
    credential_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    health_status: Mapped[AccountHealthStatus] = mapped_column(
        String(16), default=AccountHealthStatus.UNKNOWN, index=True
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CloudRegion(BaseModel):
    """``cloud_regions`` -- one region catalog entry for a provider."""

    __tablename__ = "cloud_regions"
    __table_args__ = (Index("ix_cloud_region_provider", "provider_id"),)

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_providers.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class CloudProject(BaseModel):
    """``cloud_projects`` -- one provider-side sub-grouping within an
    account (a GCP project, an Azure resource group, an AWS
    organizational unit)."""

    __tablename__ = "cloud_projects"
    __table_args__ = (Index("ix_cloud_project_account", "account_id"),)

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True
    )
    external_project_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))


__all__ = ["CloudAccount", "CloudProject", "CloudProvider", "CloudRegion"]
