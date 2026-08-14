"""The repository bundle every route works through.

One object rather than twenty-seven constructor arguments, all sharing
one tenant scope: a bundle where one repository was built without it
would enforce tenant isolation everywhere except the one query that
forgot, and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.billing import (
    BillingAccountRepository,
    CreditRepository,
    DiscountRepository,
    InvoiceItemRepository,
    InvoiceRepository,
    MarketplaceSubscriptionRepository,
    PaymentMethodRepository,
    PaymentTransactionRepository,
    PromotionRepository,
)
from app.repositories.contracts import ContractRepository
from app.repositories.customers import CustomerAccountRepository, CustomerRepository
from app.repositories.licenses import (
    LicenseActivationRepository,
    LicenseEntitlementRepository,
    LicenseKeyRepository,
    LicenseRepository,
    OfflineLicenseRepository,
)
from app.repositories.reporting import (
    BillingAuditRepository,
    BillingReportRepository,
    BillingStatisticRepository,
)
from app.repositories.subscriptions import (
    SubscriptionFeatureRepository,
    SubscriptionPlanRepository,
    SubscriptionRepository,
)
from app.repositories.usage import (
    QuotaRepository,
    QuotaUsageRepository,
    UsageCounterRepository,
    UsageRecordRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    customers: CustomerRepository
    customer_accounts: CustomerAccountRepository

    plans: SubscriptionPlanRepository
    plan_features: SubscriptionFeatureRepository
    subscriptions: SubscriptionRepository

    licenses: LicenseRepository
    license_keys: LicenseKeyRepository
    license_activations: LicenseActivationRepository
    license_entitlements: LicenseEntitlementRepository
    offline_licenses: OfflineLicenseRepository

    contracts: ContractRepository

    usage_records: UsageRecordRepository
    usage_counters: UsageCounterRepository
    quotas: QuotaRepository
    quota_usage: QuotaUsageRepository

    billing_accounts: BillingAccountRepository
    payment_methods: PaymentMethodRepository
    payment_transactions: PaymentTransactionRepository
    invoices: InvoiceRepository
    invoice_items: InvoiceItemRepository
    credits: CreditRepository
    discounts: DiscountRepository
    promotions: PromotionRepository
    marketplace_subscriptions: MarketplaceSubscriptionRepository

    statistics: BillingStatisticRepository
    reports: BillingReportRepository
    audit: BillingAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        customers=CustomerRepository(session, tenant_scope=tenant_scope),
        customer_accounts=CustomerAccountRepository(session, tenant_scope=tenant_scope),
        plans=SubscriptionPlanRepository(session, tenant_scope=tenant_scope),
        plan_features=SubscriptionFeatureRepository(session, tenant_scope=tenant_scope),
        subscriptions=SubscriptionRepository(session, tenant_scope=tenant_scope),
        licenses=LicenseRepository(session, tenant_scope=tenant_scope),
        license_keys=LicenseKeyRepository(session, tenant_scope=tenant_scope),
        license_activations=LicenseActivationRepository(session, tenant_scope=tenant_scope),
        license_entitlements=LicenseEntitlementRepository(session, tenant_scope=tenant_scope),
        offline_licenses=OfflineLicenseRepository(session, tenant_scope=tenant_scope),
        contracts=ContractRepository(session, tenant_scope=tenant_scope),
        usage_records=UsageRecordRepository(session, tenant_scope=tenant_scope),
        usage_counters=UsageCounterRepository(session, tenant_scope=tenant_scope),
        quotas=QuotaRepository(session, tenant_scope=tenant_scope),
        quota_usage=QuotaUsageRepository(session, tenant_scope=tenant_scope),
        billing_accounts=BillingAccountRepository(session, tenant_scope=tenant_scope),
        payment_methods=PaymentMethodRepository(session, tenant_scope=tenant_scope),
        payment_transactions=PaymentTransactionRepository(session, tenant_scope=tenant_scope),
        invoices=InvoiceRepository(session, tenant_scope=tenant_scope),
        invoice_items=InvoiceItemRepository(session, tenant_scope=tenant_scope),
        credits=CreditRepository(session, tenant_scope=tenant_scope),
        discounts=DiscountRepository(session, tenant_scope=tenant_scope),
        promotions=PromotionRepository(session, tenant_scope=tenant_scope),
        marketplace_subscriptions=MarketplaceSubscriptionRepository(
            session, tenant_scope=tenant_scope
        ),
        statistics=BillingStatisticRepository(session, tenant_scope=tenant_scope),
        reports=BillingReportRepository(session, tenant_scope=tenant_scope),
        audit=BillingAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
