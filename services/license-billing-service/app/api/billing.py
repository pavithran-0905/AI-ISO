"""The 17 docs/069 REST endpoints.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from shared_core.exceptions.conflict import ConflictError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CurrentUserId,
    InvoiceServiceDep,
    LicenseServiceDep,
    OrganizationId,
    PaymentServiceDep,
    Repos,
    ServiceSettings,
    SubscriptionServiceDep,
    require_administrator,
)
from app.models.billing import Invoice, PaymentTransaction
from app.models.enums import LicenseStatus, SubscriptionStatus
from app.models.licenses import License
from app.models.subscriptions import Subscription
from app.schemas.billing import (
    MAX_PAGE_SIZE,
    InvoiceCreateRequest,
    InvoiceResponse,
    InvoicesResponse,
    LicenseActivateRequest,
    LicenseActivationResponse,
    LicenseCreateRequest,
    LicenseResponse,
    LicensesResponse,
    PageInfo,
    PaymentCreateRequest,
    PaymentResponse,
    PaymentsResponse,
    QuotaResponse,
    QuotasResponse,
    ReportResponse,
    ReportsResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionsResponse,
    SubscriptionUpdateRequest,
    UsageCounterResponse,
    UsageResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.invoices import InvoiceItemInput
from app.services.licenses import SeatLimitReachedError
from app.services.licenses import TransitionRefusedError as LicenseTransitionRefusedError
from app.services.subscriptions import TransitionRefusedError as SubscriptionTransitionRefusedError

router = APIRouter(tags=["License & Billing"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _license_response(license_row: License) -> LicenseResponse:
    return LicenseResponse(
        id=license_row.id,
        customer_id=license_row.customer_id,
        subscription_id=license_row.subscription_id,
        license_model=license_row.license_model,
        status=license_row.status,
        issued_at=license_row.issued_at,
        expires_at=license_row.expires_at,
        seat_limit=license_row.seat_limit,
    )


def _subscription_response(subscription: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        customer_id=subscription.customer_id,
        plan_id=subscription.plan_id,
        status=subscription.status,
        start_at=subscription.start_at,
        end_at=subscription.end_at,
        auto_renew=subscription.auto_renew,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
    )


def _invoice_response(invoice: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        billing_account_id=invoice.billing_account_id,
        subscription_id=invoice.subscription_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        issued_at=invoice.issued_at,
        due_at=invoice.due_at,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
    )


def _payment_response(transaction: PaymentTransaction) -> PaymentResponse:
    return PaymentResponse(
        id=transaction.id,
        billing_account_id=transaction.billing_account_id,
        payment_method_id=transaction.payment_method_id,
        invoice_id=transaction.invoice_id,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        attempt_count=transaction.attempt_count,
        processed_at=transaction.processed_at,
    )


# ---- GET/POST /licenses, /licenses/{id}, .../activate, .../revoke ---------------------------


@router.get("/licenses", response_model=SuccessResponse[LicensesResponse], summary="List licenses")
async def list_licenses(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[LicensesResponse]:
    rows = await repos.licenses.list_recent(organization_id, limit=limit)
    data = LicensesResponse(
        licenses=[_license_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Licenses retrieved.", data=data, meta=_meta())


@router.post(
    "/licenses",
    response_model=SuccessResponse[LicenseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Issue a license",
    dependencies=[Depends(require_administrator)],
)
async def create_license(
    organization_id: OrganizationId,
    license_service: LicenseServiceDep,
    body: LicenseCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[LicenseResponse]:
    license_row = await license_service.issue_license(
        organization_id,
        customer_id=body.customer_id,
        subscription_id=body.subscription_id,
        license_model=body.license_model,
        expires_at=body.expires_at,
        seat_limit=body.seat_limit,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="License issued.", data=_license_response(license_row), meta=_meta()
    )


@router.get(
    "/licenses/{license_id}",
    response_model=SuccessResponse[LicenseResponse],
    summary="Get a license",
)
async def get_license(
    organization_id: OrganizationId, repos: Repos, license_id: UUID
) -> SuccessResponse[LicenseResponse]:
    license_row = await repos.licenses.require_in_org(organization_id, license_id)
    return SuccessResponse(
        message="License retrieved.", data=_license_response(license_row), meta=_meta()
    )


@router.post(
    "/licenses/{license_id}/activate",
    response_model=SuccessResponse[LicenseActivationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Activate a license seat",
)
async def activate_license(
    organization_id: OrganizationId,
    repos: Repos,
    license_service: LicenseServiceDep,
    license_id: UUID,
    body: LicenseActivateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[LicenseActivationResponse]:
    license_row = await repos.licenses.require_in_org(organization_id, license_id)
    try:
        activation = await license_service.activate_seat(
            license_row, activation_ref=body.activation_ref, actor_id=actor, now=datetime.now(UTC)
        )
    except SeatLimitReachedError as exc:
        raise ConflictError(str(exc)) from exc
    data = LicenseActivationResponse(
        id=activation.id,
        license_id=activation.license_id,
        activation_ref=activation.activation_ref,
        activated_at=activation.activated_at,
        is_enabled=activation.is_enabled,
    )
    return SuccessResponse(message="License activated.", data=data, meta=_meta())


@router.post(
    "/licenses/{license_id}/revoke",
    response_model=SuccessResponse[LicenseResponse],
    summary="Revoke a license",
    dependencies=[Depends(require_administrator)],
)
async def revoke_license(
    organization_id: OrganizationId,
    repos: Repos,
    license_service: LicenseServiceDep,
    license_id: UUID,
    actor: CurrentUserId,
) -> SuccessResponse[LicenseResponse]:
    license_row = await repos.licenses.require_in_org(organization_id, license_id)
    try:
        license_row = await license_service.transition(
            license_row, target=LicenseStatus.REVOKED, actor_id=actor, now=datetime.now(UTC)
        )
    except LicenseTransitionRefusedError as exc:
        raise ConflictError(
            f"License {license_id!s} cannot be revoked right now: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="License revoked.", data=_license_response(license_row), meta=_meta()
    )


# ---- GET/POST /subscriptions, PUT/DELETE /subscriptions/{id} --------------------------------


@router.get(
    "/subscriptions",
    response_model=SuccessResponse[SubscriptionsResponse],
    summary="List subscriptions",
)
async def list_subscriptions(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SubscriptionsResponse]:
    rows = await repos.subscriptions.list_recent(organization_id, limit=limit)
    data = SubscriptionsResponse(
        subscriptions=[_subscription_response(row) for row in rows],
        total=len(rows),
        page=PageInfo(),
    )
    return SuccessResponse(message="Subscriptions retrieved.", data=data, meta=_meta())


@router.post(
    "/subscriptions",
    response_model=SuccessResponse[SubscriptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a subscription",
    dependencies=[Depends(require_administrator)],
)
async def create_subscription(
    organization_id: OrganizationId,
    subscription_service: SubscriptionServiceDep,
    body: SubscriptionCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[SubscriptionResponse]:
    subscription = await subscription_service.create_subscription(
        organization_id,
        customer_id=body.customer_id,
        plan_id=body.plan_id,
        start_at=body.start_at,
        current_period_end=body.current_period_end,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Subscription created.", data=_subscription_response(subscription), meta=_meta()
    )


@router.put(
    "/subscriptions/{subscription_id}",
    response_model=SuccessResponse[SubscriptionResponse],
    summary="Advance a subscription's lifecycle",
    dependencies=[Depends(require_administrator)],
)
async def update_subscription(
    organization_id: OrganizationId,
    repos: Repos,
    subscription_service: SubscriptionServiceDep,
    subscription_id: UUID,
    body: SubscriptionUpdateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[SubscriptionResponse]:
    subscription = await repos.subscriptions.require_in_org(organization_id, subscription_id)
    try:
        subscription = await subscription_service.transition(
            subscription, target=body.target_status, actor_id=actor, now=datetime.now(UTC)
        )
    except SubscriptionTransitionRefusedError as exc:
        raise ConflictError(
            f"Subscription {subscription_id!s} cannot move to {body.target_status.value}: "
            f"{exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Subscription updated.", data=_subscription_response(subscription), meta=_meta()
    )


@router.delete(
    "/subscriptions/{subscription_id}",
    response_model=SuccessResponse[SubscriptionResponse],
    summary="Cancel a subscription",
    dependencies=[Depends(require_administrator)],
)
async def delete_subscription(
    organization_id: OrganizationId,
    repos: Repos,
    subscription_service: SubscriptionServiceDep,
    subscription_id: UUID,
    actor: CurrentUserId,
) -> SuccessResponse[SubscriptionResponse]:
    subscription = await repos.subscriptions.require_in_org(organization_id, subscription_id)
    try:
        subscription = await subscription_service.transition(
            subscription, target=SubscriptionStatus.CANCELLED, actor_id=actor, now=datetime.now(UTC)
        )
    except SubscriptionTransitionRefusedError as exc:
        raise ConflictError(
            f"Subscription {subscription_id!s} cannot be cancelled right now: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Subscription cancelled.", data=_subscription_response(subscription), meta=_meta()
    )


# ---- GET/POST /billing/invoices ---------------------------------------------------------------


@router.get(
    "/billing/invoices", response_model=SuccessResponse[InvoicesResponse], summary="List invoices"
)
async def list_invoices(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[InvoicesResponse]:
    rows = await repos.invoices.list_recent(organization_id, limit=limit)
    data = InvoicesResponse(
        invoices=[_invoice_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Invoices retrieved.", data=data, meta=_meta())


@router.post(
    "/billing/invoices",
    response_model=SuccessResponse[InvoiceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate an invoice",
    dependencies=[Depends(require_administrator)],
)
async def create_invoice(
    organization_id: OrganizationId,
    invoice_service: InvoiceServiceDep,
    settings: ServiceSettings,
    body: InvoiceCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[InvoiceResponse]:
    invoice = await invoice_service.generate(
        organization_id,
        billing_account_id=body.billing_account_id,
        subscription_id=body.subscription_id,
        invoice_number=body.invoice_number,
        items=[
            InvoiceItemInput(
                description=item.description, quantity=item.quantity, unit_price=item.unit_price
            )
            for item in body.items
        ],
        currency=body.currency,
        due_days=settings.invoice_due_days,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Invoice generated.", data=_invoice_response(invoice), meta=_meta()
    )


# ---- GET/POST /billing/payments ---------------------------------------------------------------


@router.get(
    "/billing/payments",
    response_model=SuccessResponse[PaymentsResponse],
    summary="List payment transactions",
)
async def list_payments(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[PaymentsResponse]:
    rows = await repos.payment_transactions.list_recent(organization_id, limit=limit)
    data = PaymentsResponse(
        payments=[_payment_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Payments retrieved.", data=data, meta=_meta())


@router.post(
    "/billing/payments",
    response_model=SuccessResponse[PaymentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment attempt",
    dependencies=[Depends(require_administrator)],
)
async def create_payment(
    organization_id: OrganizationId,
    payment_service: PaymentServiceDep,
    body: PaymentCreateRequest,
) -> SuccessResponse[PaymentResponse]:
    transaction = await payment_service.record_attempt(
        organization_id,
        billing_account_id=body.billing_account_id,
        payment_method_id=body.payment_method_id,
        invoice_id=body.invoice_id,
        amount=body.amount,
        currency=body.currency,
    )
    now = datetime.now(UTC)
    if body.succeeded:
        transaction = await payment_service.mark_succeeded(transaction, now=now)
    else:
        transaction = await payment_service.mark_failed(transaction, now=now)
    return SuccessResponse(
        message="Payment recorded.", data=_payment_response(transaction), meta=_meta()
    )


# ---- GET /billing/usage, /billing/quotas, /billing/statistics, /billing/reports --------------


@router.get(
    "/billing/usage", response_model=SuccessResponse[UsageResponse], summary="Usage counters"
)
async def get_usage(
    organization_id: OrganizationId, repos: Repos, customer_id: UUID
) -> SuccessResponse[UsageResponse]:
    await repos.customers.require_in_org(organization_id, customer_id)
    rows = await repos.usage_counters.list_for_customer(customer_id)
    data = UsageResponse(
        counters=[
            UsageCounterResponse(
                customer_id=row.customer_id,
                metric_key=row.metric_key,
                period_start=row.period_start,
                period_end=row.period_end,
                total_quantity=row.total_quantity,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Usage retrieved.", data=data, meta=_meta())


@router.get("/billing/quotas", response_model=SuccessResponse[QuotasResponse], summary="Quotas")
async def get_quotas(
    organization_id: OrganizationId, repos: Repos, customer_id: UUID | None = None
) -> SuccessResponse[QuotasResponse]:
    rows = (
        await repos.quotas.list_for_customer(customer_id)
        if customer_id is not None
        else await repos.quotas.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    )
    data = QuotasResponse(
        quotas=[
            QuotaResponse(
                id=row.id,
                customer_id=row.customer_id,
                metric_key=row.metric_key,
                limit_value=row.limit_value,
                limit_kind=str(row.limit_kind),
                period=str(row.period),
                burst_limit=row.burst_limit,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Quotas retrieved.", data=data, meta=_meta())


@router.get(
    "/billing/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Fleet statistics",
)
async def get_statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or _default_window(7)[0]
    rows = await repos.statistics.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                mrr=row.mrr,
                arr=row.arr,
                active_subscriptions=row.active_subscriptions,
                churned_subscriptions=row.churned_subscriptions,
                invoices_generated=row.invoices_generated,
                payments_received=row.payments_received,
                payments_failed=row.payments_failed,
                quota_exceeded_count=row.quota_exceeded_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Fleet statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/billing/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def get_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(
        reports=[
            ReportResponse(
                id=row.id,
                kind=row.kind,
                report_format=row.report_format,
                title=row.title,
                status=row.status,
                period_start=row.period_start,
                period_end=row.period_end,
                generated_at=row.generated_at,
                row_count=row.row_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


__all__ = ["router"]
