"""Developer accounts and the third-party organizations that own them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DeveloperAccountStatus, DeveloperOrganizationStatus


class DeveloperOrganization(BaseModel):
    """``developer_organizations`` -- one third-party company that owns
    developer accounts within this platform tenant.

    Distinct from ``organization_id`` (``BaseEntityMixin``'s own
    reserved tenant-scoping column, which is the AI-IOS *platform
    tenant* operating this developer platform instance) -- a
    ``DeveloperOrganization`` is an external company (a partner, an
    ISV, an OEM) this tenant's developer platform onboards, the same
    "own administrative view of an external concept" resolution
    ``services/administration-portal-service`` used for its own
    ``Organization``/``Tenant`` tables in Prompt 070.
    """

    __tablename__ = "developer_organizations"
    __table_args__ = (Index("ix_developer_organization_name", "name"),)

    name: Mapped[str] = mapped_column(String(256), index=True)
    status: Mapped[DeveloperOrganizationStatus] = mapped_column(
        String(16), default=DeveloperOrganizationStatus.ACTIVE, index=True
    )


class DeveloperAccount(BaseModel):
    """``developer_accounts`` -- one registered external developer."""

    __tablename__ = "developer_accounts"
    __table_args__ = (Index("ix_developer_account_status", "status"),)

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    developer_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("developer_organizations.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[DeveloperAccountStatus] = mapped_column(
        String(24), default=DeveloperAccountStatus.PENDING_VERIFICATION, index=True
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["DeveloperAccount", "DeveloperOrganization"]
