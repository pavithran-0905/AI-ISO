"""Enumerations for the license & billing service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every other
AI-IOS service's convention), and comparable with ``==`` against a value
freshly loaded from the database, which comes back as a plain ``str``
rather than the enum instance itself -- see
``services/multi-cluster-management-service``'s own hard-won lesson on
why ``is`` comparison against such a value is unsafe.
"""

from __future__ import annotations

from enum import StrEnum


class CustomerType(StrEnum):
    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    BUSINESS_UNIT = "business_unit"
    RESELLER = "reseller"
    PARTNER = "partner"
    MSP = "msp"
    OEM = "oem"


class CustomerAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class BillingModel(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    USAGE_BASED = "usage_based"
    CONSUMPTION_BASED = "consumption_based"
    TIERED = "tiered"
    FLAT_RATE = "flat_rate"
    PAY_AS_YOU_GO = "pay_as_you_go"
    PREPAID = "prepaid"
    HYBRID = "hybrid"
    CUSTOM = "custom"


class SubscriptionStatus(StrEnum):
    """A subscription's position in its own lifecycle -- see
    ``app.subscriptions.engine`` for the transition table this drives."""

    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_RENEWAL = "pending_renewal"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class LicenseModel(StrEnum):
    SAAS = "saas"
    PERPETUAL = "perpetual"
    TERM = "term"
    EVALUATION = "evaluation"
    TRIAL = "trial"
    ENTERPRISE = "enterprise"
    SITE = "site"
    OEM = "oem"
    ACADEMIC = "academic"
    MSP = "msp"
    CONSUMPTION = "consumption"
    BYOL = "byol"
    OFFLINE = "offline"
    FLOATING = "floating"
    NAMED_USER = "named_user"


class LicenseStatus(StrEnum):
    """A license's position in its own lifecycle -- see
    ``app.licenses.engine`` for the transition table this drives."""

    ISSUED = "issued"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ContractStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuotaLimitKind(StrEnum):
    SOFT = "soft"
    HARD = "hard"


class QuotaPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class PaymentMethodType(StrEnum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    PURCHASE_ORDER = "purchase_order"
    INVOICE = "invoice"
    MANUAL = "manual"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class DiscountType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class MarketplaceSubscriptionStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ReportKind(StrEnum):
    REVENUE = "revenue"
    USAGE = "usage"
    SUBSCRIPTION = "subscription"
    INVOICE = "invoice"
    RENEWAL = "renewal"
    QUOTA = "quota"
    LICENSE = "license"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(StrEnum):
    """What was done, for the immutable billing audit trail."""

    LICENSE_CREATED = "license_created"
    LICENSE_ACTIVATED = "license_activated"
    SUBSCRIPTION_CHANGED = "subscription_changed"
    BILLING_CHANGED = "billing_changed"
    INVOICE_GENERATED = "invoice_generated"
    PAYMENT_EVENT = "payment_event"
    CONTRACT_CHANGED = "contract_changed"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "ApprovalStatus",
    "AuditAction",
    "BillingModel",
    "ContractStatus",
    "CustomerAccountStatus",
    "CustomerType",
    "DiscountType",
    "InvoiceStatus",
    "LicenseModel",
    "LicenseStatus",
    "MarketplaceSubscriptionStatus",
    "PaymentMethodType",
    "PaymentStatus",
    "QuotaLimitKind",
    "QuotaPeriod",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SubscriptionStatus",
]
