"""FastAPI dependency injection for the license & billing service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their customers and licenses -- or worse, able to issue a
license against them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.database.session import session_scope
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import LicenseBillingServiceSettings
from app.services.audit import AuditService
from app.services.billing_accounts import BillingAccountService, PaymentMethodService
from app.services.bundle import Repositories, build_repositories
from app.services.contracts import ContractService
from app.services.customers import CustomerAccountService, CustomerService
from app.services.entitlements import LicenseEntitlementService, SubscriptionFeatureService
from app.services.invoices import InvoiceService
from app.services.licenses import LicenseService
from app.services.marketplace import MarketplaceSubscriptionService
from app.services.offline import OfflineLicenseService
from app.services.payments import PaymentService
from app.services.pricing import DiscountService, PromotionService
from app.services.quotas import QuotaService
from app.services.reports import ReportService
from app.services.statistics import StatisticsService
from app.services.subscriptions import SubscriptionPlanService, SubscriptionService
from app.services.usage import UsageService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset(
    {"admin", "administrator", "platform_admin", "billing_admin", "license_admin"}
)
"""Roles permitted to issue/revoke licenses, manage subscriptions, and
generate invoices/payments. Never across organizations: an
administrator's remit is their tenant."""

_ROLES_CLAIM = "roles"
_ORGANIZATION_CLAIM = "organization_id"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session, committing on success."""
    session_factory = request.app.state.db_session_factory
    async with session_scope(session_factory) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_event_publisher(request: Request) -> EventPublisher:
    return request.app.state.publish_event  # type: ignore[no-any-return]


EventPublisherDep = Annotated[EventPublisher, Depends(get_event_publisher)]


def get_service_settings(request: Request) -> LicenseBillingServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[LicenseBillingServiceSettings, Depends(get_service_settings)]


# ---- authentication -----------------------------------------------------------------


async def get_token_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    if credentials is None:
        raise AuthenticationError("Authentication required.")
    public_key = request.app.state.jwt_public_key
    return dict(decode_token(credentials.credentials, public_key=public_key))


TokenClaims = Annotated[dict[str, Any], Depends(get_token_claims)]


async def get_current_user_id(claims: TokenClaims) -> str:
    subject = claims.get("sub")
    if not subject:
        raise AuthenticationError("The token carries no valid subject claim.")
    return str(subject)


CurrentUserId = Annotated[str, Depends(get_current_user_id)]


async def get_organization_id(claims: TokenClaims) -> UUID:
    raw = claims.get(_ORGANIZATION_CLAIM)
    if not raw:
        raise AuthorizationError(
            "The token carries no organization claim, so no tenant scope can be established."
        )
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise AuthorizationError(
            f"The token's organization claim {raw!r} is not a valid identifier."
        ) from exc


OrganizationId = Annotated[UUID, Depends(get_organization_id)]


async def get_roles(claims: TokenClaims) -> frozenset[str]:
    raw = claims.get(_ROLES_CLAIM) or []
    if isinstance(raw, str):
        raw = [raw]
    return frozenset(str(role).strip().lower() for role in raw if str(role).strip())


Roles = Annotated[frozenset[str], Depends(get_roles)]


async def require_administrator(roles: Roles) -> None:
    if not roles & ADMINISTRATOR_ROLES:
        raise AuthorizationError("You do not have permission to perform this action.")


# ---- repositories and services -------------------------------------------------------------


def get_repos(session: DbSession, organization_id: OrganizationId) -> Repositories:
    return build_repositories(session, tenant_scope=TenantScope(organization_id=organization_id))


Repos = Annotated[Repositories, Depends(get_repos)]


def get_audit_service(repos: Repos) -> AuditService:
    return AuditService(repos.audit)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_customer_service(repos: Repos, publish: EventPublisherDep) -> CustomerService:
    return CustomerService(repos.customers, publish=publish)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


def get_customer_account_service(repos: Repos) -> CustomerAccountService:
    return CustomerAccountService(repos.customer_accounts)


CustomerAccountServiceDep = Annotated[CustomerAccountService, Depends(get_customer_account_service)]


def get_plan_service(repos: Repos) -> SubscriptionPlanService:
    return SubscriptionPlanService(repos.plans)


PlanServiceDep = Annotated[SubscriptionPlanService, Depends(get_plan_service)]


def get_subscription_feature_service(repos: Repos) -> SubscriptionFeatureService:
    return SubscriptionFeatureService(repos.plan_features)


SubscriptionFeatureServiceDep = Annotated[
    SubscriptionFeatureService, Depends(get_subscription_feature_service)
]


def get_subscription_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> SubscriptionService:
    return SubscriptionService(repos.subscriptions, publish=publish, audit=audit)


SubscriptionServiceDep = Annotated[SubscriptionService, Depends(get_subscription_service)]


def get_license_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> LicenseService:
    return LicenseService(repos.licenses, repos.license_activations, publish=publish, audit=audit)


LicenseServiceDep = Annotated[LicenseService, Depends(get_license_service)]


def get_license_entitlement_service(repos: Repos) -> LicenseEntitlementService:
    return LicenseEntitlementService(repos.license_entitlements)


LicenseEntitlementServiceDep = Annotated[
    LicenseEntitlementService, Depends(get_license_entitlement_service)
]


def get_offline_license_service(repos: Repos) -> OfflineLicenseService:
    return OfflineLicenseService(repos.offline_licenses)


OfflineLicenseServiceDep = Annotated[OfflineLicenseService, Depends(get_offline_license_service)]


def get_contract_service(repos: Repos, audit: AuditServiceDep) -> ContractService:
    return ContractService(repos.contracts, audit=audit)


ContractServiceDep = Annotated[ContractService, Depends(get_contract_service)]


def get_usage_service(repos: Repos) -> UsageService:
    return UsageService(repos.usage_records, repos.usage_counters)


UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]


def get_quota_service(repos: Repos, publish: EventPublisherDep) -> QuotaService:
    return QuotaService(repos.quotas, repos.quota_usage, publish=publish)


QuotaServiceDep = Annotated[QuotaService, Depends(get_quota_service)]


def get_billing_account_service(repos: Repos) -> BillingAccountService:
    return BillingAccountService(repos.billing_accounts)


BillingAccountServiceDep = Annotated[BillingAccountService, Depends(get_billing_account_service)]


def get_payment_method_service(repos: Repos) -> PaymentMethodService:
    return PaymentMethodService(repos.payment_methods)


PaymentMethodServiceDep = Annotated[PaymentMethodService, Depends(get_payment_method_service)]


def get_payment_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> PaymentService:
    return PaymentService(repos.payment_transactions, publish=publish, audit=audit)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


def get_invoice_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> InvoiceService:
    return InvoiceService(repos.invoices, repos.invoice_items, publish=publish, audit=audit)


InvoiceServiceDep = Annotated[InvoiceService, Depends(get_invoice_service)]


def get_discount_service(repos: Repos) -> DiscountService:
    return DiscountService(repos.discounts)


DiscountServiceDep = Annotated[DiscountService, Depends(get_discount_service)]


def get_promotion_service(repos: Repos) -> PromotionService:
    return PromotionService(repos.promotions)


PromotionServiceDep = Annotated[PromotionService, Depends(get_promotion_service)]


def get_marketplace_service(
    repos: Repos, publish: EventPublisherDep
) -> MarketplaceSubscriptionService:
    return MarketplaceSubscriptionService(repos.marketplace_subscriptions, publish=publish)


MarketplaceServiceDep = Annotated[MarketplaceSubscriptionService, Depends(get_marketplace_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
