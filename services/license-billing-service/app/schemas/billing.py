"""Request/response schemas for the 17 docs/069 REST routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    InvoiceStatus,
    LicenseModel,
    LicenseStatus,
    PaymentStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SubscriptionStatus,
)

MAX_PAGE_SIZE = 500


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class PageInfo(_Base):
    has_more: bool = False


# ---- licenses -----------------------------------------------------------------------------


class LicenseCreateRequest(_Base):
    customer_id: UUID
    subscription_id: UUID | None = None
    license_model: LicenseModel
    expires_at: datetime | None = None
    seat_limit: int | None = None


class LicenseResponse(_Base):
    id: UUID
    customer_id: UUID
    subscription_id: UUID | None
    license_model: LicenseModel
    status: LicenseStatus
    issued_at: datetime
    expires_at: datetime | None
    seat_limit: int | None


class LicensesResponse(_Base):
    licenses: list[LicenseResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


class LicenseActivateRequest(_Base):
    activation_ref: str


class LicenseActivationResponse(_Base):
    id: UUID
    license_id: UUID
    activation_ref: str
    activated_at: datetime
    is_enabled: bool


# ---- subscriptions --------------------------------------------------------------------------


class SubscriptionCreateRequest(_Base):
    customer_id: UUID
    plan_id: UUID
    start_at: datetime
    current_period_end: datetime


class SubscriptionUpdateRequest(_Base):
    target_status: SubscriptionStatus


class SubscriptionResponse(_Base):
    id: UUID
    customer_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    start_at: datetime
    end_at: datetime | None
    auto_renew: bool
    current_period_start: datetime
    current_period_end: datetime


class SubscriptionsResponse(_Base):
    subscriptions: list[SubscriptionResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- billing: invoices ---------------------------------------------------------------------


class InvoiceItemRequest(_Base):
    description: str
    quantity: float = 1.0
    unit_price: float


class InvoiceCreateRequest(_Base):
    billing_account_id: UUID
    subscription_id: UUID | None = None
    invoice_number: str
    items: list[InvoiceItemRequest]
    currency: str = "USD"


class InvoiceResponse(_Base):
    id: UUID
    billing_account_id: UUID
    subscription_id: UUID | None
    invoice_number: str
    status: InvoiceStatus
    issued_at: datetime | None
    due_at: datetime | None
    total_amount: float
    currency: str


class InvoicesResponse(_Base):
    invoices: list[InvoiceResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- billing: payments ---------------------------------------------------------------------


class PaymentCreateRequest(_Base):
    billing_account_id: UUID
    payment_method_id: UUID | None = None
    invoice_id: UUID | None = None
    amount: float
    currency: str = "USD"
    succeeded: bool
    """Whether the payment attempt succeeded -- reported by the caller
    (a gateway webhook handler, an operator); this service never
    processes a real payment itself. See this package's README "Scope
    boundary"."""


class PaymentResponse(_Base):
    id: UUID
    billing_account_id: UUID
    payment_method_id: UUID | None
    invoice_id: UUID | None
    amount: float
    currency: str
    status: PaymentStatus
    attempt_count: int
    processed_at: datetime | None


class PaymentsResponse(_Base):
    payments: list[PaymentResponse]
    total: int
    page: PageInfo = Field(default_factory=PageInfo)


# ---- billing: usage / quotas ---------------------------------------------------------------


class UsageCounterResponse(_Base):
    customer_id: UUID
    metric_key: str
    period_start: datetime
    period_end: datetime
    total_quantity: float


class UsageResponse(_Base):
    counters: list[UsageCounterResponse]
    total: int


class QuotaResponse(_Base):
    id: UUID
    customer_id: UUID
    metric_key: str
    limit_value: float
    limit_kind: str
    period: str
    burst_limit: float | None


class QuotasResponse(_Base):
    quotas: list[QuotaResponse]
    total: int


# ---- statistics / reports ------------------------------------------------------------------


class StatisticWindowResponse(_Base):
    window_start: datetime
    window_end: datetime
    mrr: float
    arr: float
    active_subscriptions: int
    churned_subscriptions: int
    invoices_generated: int
    payments_received: int
    payments_failed: int
    quota_exceeded_count: int


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
    "InvoiceCreateRequest",
    "InvoiceItemRequest",
    "InvoiceResponse",
    "InvoicesResponse",
    "LicenseActivateRequest",
    "LicenseActivationResponse",
    "LicenseCreateRequest",
    "LicenseResponse",
    "LicensesResponse",
    "PageInfo",
    "PaymentCreateRequest",
    "PaymentResponse",
    "PaymentsResponse",
    "QuotaResponse",
    "QuotasResponse",
    "ReportResponse",
    "ReportsResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "SubscriptionCreateRequest",
    "SubscriptionResponse",
    "SubscriptionUpdateRequest",
    "SubscriptionsResponse",
    "UsageCounterResponse",
    "UsageResponse",
]
