"""Customers and their sub-accounts.

**A ``Customer`` is the business entity being billed** -- an
organization, a department, a business unit, a reseller, a partner, an
MSP, or an OEM -- nested via ``parent_customer_id`` so a department
under an organization, or an end customer under an MSP/reseller, is
represented without flattening the relationship.
"""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CustomerAccountStatus, CustomerType


class Customer(BaseModel):
    """``customers`` -- one billed business entity."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customer_type", "customer_type"),
        Index("ix_customer_parent", "parent_customer_id"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    customer_type: Mapped[CustomerType] = mapped_column(String(16), index=True)
    parent_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), default=None
    )
    billing_contact_email: Mapped[str | None] = mapped_column(String(255), default=None)
    technical_contact_email: Mapped[str | None] = mapped_column(String(255), default=None)


class CustomerAccount(BaseModel):
    """``customer_accounts`` -- one external account reference under a
    customer (e.g. the AI-IOS tenant organization id this customer maps
    to)."""

    __tablename__ = "customer_accounts"
    __table_args__ = (Index("ix_customer_account_customer", "customer_id"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    external_account_ref: Mapped[str] = mapped_column(String(255), index=True)
    account_status: Mapped[CustomerAccountStatus] = mapped_column(
        String(16), default=CustomerAccountStatus.ACTIVE, index=True
    )


__all__ = ["Customer", "CustomerAccount"]
