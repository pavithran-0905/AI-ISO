"""Licenses, their keys, activations, entitlements, and offline
license files.

**A ``LicenseKey``/``LicenseActivation``/``LicenseEntitlement``'s
"currently usable" flag is named ``is_enabled``, deliberately not
``is_active``** -- ``is_active`` is one of
:class:`~shared_core.database.base.BaseEntityMixin`'s own reserved
columns (the soft-delete flag every repository's ``_base_select()``
filters on); reusing it for a domain-specific enabled/disabled flag
would silently collide, exactly the defect
``services/edge-management-service`` found and documented in Prompt
067.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import LicenseModel, LicenseStatus


class License(BaseModel):
    """``licenses`` -- one issued license, anywhere in its lifecycle
    from issuance to revocation."""

    __tablename__ = "licenses"
    __table_args__ = (
        Index("ix_license_customer", "customer_id"),
        Index("ix_license_subscription", "subscription_id"),
        Index("ix_license_model", "license_model"),
        Index("ix_license_status", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), default=None
    )
    license_model: Mapped[LicenseModel] = mapped_column(String(16), index=True)
    status: Mapped[LicenseStatus] = mapped_column(
        String(16), default=LicenseStatus.ISSUED, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    seat_limit: Mapped[int | None] = mapped_column(Integer, default=None)
    """``None`` means unlimited seats -- a floating/site license, for
    instance."""


class LicenseKey(BaseModel):
    """``license_keys`` -- one generated key value for a license."""

    __tablename__ = "license_keys"
    __table_args__ = (Index("ix_license_key_license", "license_id"),)

    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    key_value: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class LicenseActivation(BaseModel):
    """``license_activations`` -- one seat activation against a
    license (a device, a host, a named user)."""

    __tablename__ = "license_activations"
    __table_args__ = (Index("ix_license_activation_license", "license_id"),)

    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    activation_ref: Mapped[str] = mapped_column(String(255), index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class LicenseEntitlement(BaseModel):
    """``license_entitlements`` -- one feature entitlement a license
    grants, with an optional numeric limit (``None`` means unlimited)."""

    __tablename__ = "license_entitlements"
    __table_args__ = (Index("ix_license_entitlement_license", "license_id"),)

    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    feature_key: Mapped[str] = mapped_column(String(128), index=True)
    limit_value: Mapped[int | None] = mapped_column(Integer, default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class OfflineLicense(BaseModel):
    """``offline_licenses`` -- one signed license file issued for an
    air-gapped deployment."""

    __tablename__ = "offline_licenses"
    __table_args__ = (Index("ix_offline_license_license", "license_id"),)

    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    license_file_hash: Mapped[str] = mapped_column(String(128), index=True)
    """A hash of the signed license file this row tracks -- the file
    content itself is never stored here, only enough to validate it was
    not tampered with and to revoke it by reference."""
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = ["License", "LicenseActivation", "LicenseEntitlement", "LicenseKey", "OfflineLicense"]
