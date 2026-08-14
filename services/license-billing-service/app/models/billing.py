"""Billing accounts, payment methods and transactions, invoices,
credits, discounts, promotions, and marketplace subscriptions.

**``PaymentMethod.reference`` is a tokenized/masked lookup key, never
the real instrument.** This service never sees or stores a real card
number or bank account number -- that is a payment gateway's job (see
this package's README "Scope boundary"); the reference is only enough
to look the real instrument up in that gateway.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    DiscountType,
    InvoiceStatus,
    MarketplaceSubscriptionStatus,
    PaymentMethodType,
    PaymentStatus,
)


class BillingAccount(BaseModel):
    """``billing_accounts`` -- one customer's billing profile."""

    __tablename__ = "billing_accounts"
    __table_args__ = (Index("ix_billing_account_customer", "customer_id"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    tax_id: Mapped[str | None] = mapped_column(String(64), default=None)
    billing_email: Mapped[str | None] = mapped_column(String(255), default=None)


class PaymentMethod(BaseModel):
    """``payment_methods`` -- one payment instrument reference for a
    billing account."""

    __tablename__ = "payment_methods"
    __table_args__ = (Index("ix_payment_method_billing_account", "billing_account_id"),)

    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_accounts.id", ondelete="CASCADE"), index=True
    )
    method_type: Mapped[PaymentMethodType] = mapped_column(String(16))
    reference: Mapped[str | None] = mapped_column(String(255), default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentTransaction(BaseModel):
    """``payment_transactions`` -- one payment attempt."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_transaction_billing_account", "billing_account_id"),
        Index("ix_payment_transaction_status", "status"),
    )

    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_accounts.id", ondelete="CASCADE"), index=True
    )
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"), default=None
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), default=None
    )
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[PaymentStatus] = mapped_column(
        String(16), default=PaymentStatus.PENDING, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Invoice(BaseModel):
    """``invoices`` -- one generated invoice."""

    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoice_billing_account", "billing_account_id"),
        Index("ix_invoice_status", "status"),
    )

    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_accounts.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), default=None
    )
    invoice_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        String(16), default=InvoiceStatus.DRAFT, index=True
    )
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")


class InvoiceItem(BaseModel):
    """``invoice_items`` -- one line item on an invoice."""

    __tablename__ = "invoice_items"
    __table_args__ = (Index("ix_invoice_item_invoice", "invoice_id"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(512))
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)


class Credit(BaseModel):
    """``credits`` -- one prepaid or goodwill credit applied to a
    billing account."""

    __tablename__ = "credits"
    __table_args__ = (Index("ix_credit_billing_account", "billing_account_id"),)

    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_accounts.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    reason: Mapped[str | None] = mapped_column(String(512), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Discount(BaseModel):
    """``discounts`` -- one reusable discount definition."""

    __tablename__ = "discounts"
    __table_args__ = (Index("ix_discount_type", "discount_type"),)

    name: Mapped[str] = mapped_column(String(255))
    discount_type: Mapped[DiscountType] = mapped_column(String(16), index=True)
    value: Mapped[float] = mapped_column(Float)
    """A percentage (``0``-``100``) when ``discount_type`` is
    ``PERCENTAGE``, or a currency amount when ``FIXED``."""
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Promotion(BaseModel):
    """``promotions`` -- one redeemable promotional code applying a
    discount."""

    __tablename__ = "promotions"
    __table_args__ = (Index("ix_promotion_code", "code"),)

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    discount_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discounts.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, default=None)
    redemption_count: Mapped[int] = mapped_column(Integer, default=0)


class MarketplaceSubscription(BaseModel):
    """``marketplace_subscriptions`` -- one subscription purchased
    through a third-party marketplace."""

    __tablename__ = "marketplace_subscriptions"
    __table_args__ = (
        Index("ix_marketplace_subscription_customer", "customer_id"),
        Index("ix_marketplace_subscription_status", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    marketplace_ref: Mapped[str] = mapped_column(String(255), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[MarketplaceSubscriptionStatus] = mapped_column(
        String(16), default=MarketplaceSubscriptionStatus.ACTIVE, index=True
    )


__all__ = [
    "BillingAccount",
    "Credit",
    "Discount",
    "Invoice",
    "InvoiceItem",
    "MarketplaceSubscription",
    "PaymentMethod",
    "PaymentTransaction",
    "Promotion",
]
