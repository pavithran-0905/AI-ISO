"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.billing import (
    BillingAccount,
    Credit,
    Discount,
    Invoice,
    InvoiceItem,
    MarketplaceSubscription,
    PaymentMethod,
    PaymentTransaction,
    Promotion,
)
from app.models.contracts import Contract
from app.models.customers import Customer, CustomerAccount
from app.models.enums import (
    AuditAction,
    BillingModel,
    CustomerAccountStatus,
    CustomerType,
    DiscountType,
    InvoiceStatus,
    LicenseModel,
    LicenseStatus,
    MarketplaceSubscriptionStatus,
    PaymentMethodType,
    PaymentStatus,
    QuotaLimitKind,
    QuotaPeriod,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SubscriptionStatus,
)
from app.models.licenses import (
    License,
    LicenseActivation,
    LicenseEntitlement,
    LicenseKey,
    OfflineLicense,
)
from app.models.reporting import BillingAudit, BillingReport, BillingStatistic
from app.models.subscriptions import Subscription, SubscriptionFeature, SubscriptionPlan
from app.models.usage import Quota, QuotaUsage, UsageCounter, UsageRecord

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _customer(organization_id: UUID, *, name: str = "Acme Corp") -> Customer:
    return Customer(
        organization_id=organization_id, name=name, customer_type=CustomerType.ORGANIZATION
    )


def _plan(organization_id: UUID, *, name: str = "Pro") -> SubscriptionPlan:
    return SubscriptionPlan(
        organization_id=organization_id,
        name=name,
        billing_model=BillingModel.MONTHLY,
        base_price=100.0,
    )


def _subscription(organization_id: UUID, customer_id: UUID, plan_id: UUID) -> Subscription:
    return Subscription(
        organization_id=organization_id,
        customer_id=customer_id,
        plan_id=plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_at=NOW,
        current_period_start=NOW,
        current_period_end=NOW + timedelta(days=30),
    )


def _license(organization_id: UUID, customer_id: UUID) -> License:
    return License(
        organization_id=organization_id,
        customer_id=customer_id,
        license_model=LicenseModel.SAAS,
        status=LicenseStatus.ISSUED,
        issued_at=NOW,
    )


class TestCustomerRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        created = await repos.customers.create(_customer(organization_id))
        found = await repos.customers.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.customers.require_in_org(organization_id, uuid4())

    async def test_list_children(self, repos, organization_id: UUID) -> None:
        parent = await repos.customers.create(_customer(organization_id, name="Parent"))
        child = _customer(organization_id, name="Child")
        child.parent_customer_id = parent.id
        await repos.customers.create(child)
        found = await repos.customers.list_children(parent.id)
        assert len(found) == 1

    async def test_list_recent_and_organization_ids(self, repos, organization_id: UUID) -> None:
        await repos.customers.create(_customer(organization_id))
        found = await repos.customers.list_recent(organization_id)
        assert len(found) == 1
        ids = await repos.customers.list_organization_ids()
        assert organization_id in ids


class TestCustomerAccountRepository:
    async def test_list_for_customer(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        await repos.customer_accounts.create(
            CustomerAccount(
                organization_id=organization_id,
                customer_id=customer.id,
                external_account_ref="ext-1",
                account_status=CustomerAccountStatus.ACTIVE,
            )
        )
        found = await repos.customer_accounts.list_for_customer(customer.id)
        assert len(found) == 1


class TestSubscriptionPlanRepository:
    async def test_list_enabled(self, repos, organization_id: UUID) -> None:
        await repos.plans.create(_plan(organization_id))
        disabled = _plan(organization_id, name="Legacy")
        disabled.is_enabled = False
        await repos.plans.create(disabled)
        found = await repos.plans.list_enabled(organization_id)
        assert len(found) == 1


class TestSubscriptionFeatureRepository:
    async def test_list_for_plan_and_find_by_key(self, repos, organization_id: UUID) -> None:
        plan = await repos.plans.create(_plan(organization_id))
        await repos.plan_features.create(
            SubscriptionFeature(
                organization_id=organization_id,
                plan_id=plan.id,
                feature_key="sso",
                limit_value=None,
            )
        )
        found = await repos.plan_features.list_for_plan(plan.id)
        assert len(found) == 1
        by_key = await repos.plan_features.find_by_key(plan.id, feature_key="sso")
        assert by_key is not None


class TestSubscriptionRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        created = await repos.subscriptions.create(
            _subscription(organization_id, customer.id, plan.id)
        )
        found = await repos.subscriptions.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.subscriptions.require_in_org(organization_id, uuid4())

    async def test_list_for_customer(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(_subscription(organization_id, customer.id, plan.id))
        found = await repos.subscriptions.list_for_customer(customer.id)
        assert len(found) == 1

    async def test_list_recent_by_status(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(_subscription(organization_id, customer.id, plan.id))
        found = await repos.subscriptions.list_recent(
            organization_id, status=SubscriptionStatus.ACTIVE
        )
        assert len(found) == 1

    async def test_list_by_status_and_organization_ids(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(_subscription(organization_id, customer.id, plan.id))
        found = await repos.subscriptions.list_by_status(
            organization_id, status=SubscriptionStatus.ACTIVE
        )
        assert len(found) == 1
        ids = await repos.subscriptions.list_organization_ids()
        assert organization_id in ids


class TestLicenseRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        created = await repos.licenses.create(_license(organization_id, customer.id))
        found = await repos.licenses.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.licenses.require_in_org(organization_id, uuid4())

    async def test_list_for_customer(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        await repos.licenses.create(_license(organization_id, customer.id))
        found = await repos.licenses.list_for_customer(customer.id)
        assert len(found) == 1

    async def test_list_recent_by_status_and_organization_ids(
        self, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        await repos.licenses.create(_license(organization_id, customer.id))
        found = await repos.licenses.list_recent(organization_id, status=LicenseStatus.ISSUED)
        assert len(found) == 1
        by_status = await repos.licenses.list_by_status(
            organization_id, status=LicenseStatus.ISSUED
        )
        assert len(by_status) == 1
        ids = await repos.licenses.list_organization_ids()
        assert organization_id in ids


class TestLicenseKeyRepository:
    async def test_list_for_license_and_find_by_value(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(_license(organization_id, customer.id))
        await repos.license_keys.create(
            LicenseKey(
                organization_id=organization_id, license_id=license_row.id, key_value="KEY-1"
            )
        )
        found = await repos.license_keys.list_for_license(license_row.id)
        assert len(found) == 1
        by_value = await repos.license_keys.find_by_value(organization_id, key_value="KEY-1")
        assert by_value is not None


class TestLicenseActivationRepository:
    async def test_list_for_license_and_count_active(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(_license(organization_id, customer.id))
        await repos.license_activations.create(
            LicenseActivation(
                organization_id=organization_id,
                license_id=license_row.id,
                activation_ref="device-1",
                activated_at=NOW,
            )
        )
        found = await repos.license_activations.list_for_license(license_row.id)
        assert len(found) == 1
        active_count = await repos.license_activations.count_active(license_row.id)
        assert active_count == 1


class TestLicenseEntitlementRepository:
    async def test_list_for_license_and_find_by_key(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(_license(organization_id, customer.id))
        await repos.license_entitlements.create(
            LicenseEntitlement(
                organization_id=organization_id, license_id=license_row.id, feature_key="api_access"
            )
        )
        found = await repos.license_entitlements.list_for_license(license_row.id)
        assert len(found) == 1
        by_key = await repos.license_entitlements.find_by_key(
            license_row.id, feature_key="api_access"
        )
        assert by_key is not None


class TestOfflineLicenseRepository:
    async def test_list_for_license(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(_license(organization_id, customer.id))
        await repos.offline_licenses.create(
            OfflineLicense(
                organization_id=organization_id,
                license_id=license_row.id,
                license_file_hash="abc123",
                issued_at=NOW,
                expires_at=NOW + timedelta(days=365),
            )
        )
        found = await repos.offline_licenses.list_for_license(license_row.id)
        assert len(found) == 1


class TestContractRepository:
    async def test_require_by_id_and_list(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        created = await repos.contracts.create(
            Contract(
                organization_id=organization_id, customer_id=customer.id, name="Enterprise Deal"
            )
        )
        found = await repos.contracts.require_by_id(created.id)
        assert found.id == created.id
        for_customer = await repos.contracts.list_for_customer(customer.id)
        assert len(for_customer) == 1
        recent = await repos.contracts.list_recent(organization_id)
        assert len(recent) == 1

    async def test_require_by_id_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.contracts.require_by_id(uuid4())


class TestUsageRecordRepository:
    async def test_list_for_customer(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        await repos.usage_records.create(
            UsageRecord(
                organization_id=organization_id,
                customer_id=customer.id,
                metric_key="api_calls",
                quantity=10.0,
                recorded_at=NOW,
            )
        )
        found = await repos.usage_records.list_for_customer(
            customer.id, since=NOW - timedelta(hours=1)
        )
        assert len(found) == 1
        by_metric = await repos.usage_records.list_for_customer(
            customer.id, metric_key="api_calls", since=NOW - timedelta(hours=1)
        )
        assert len(by_metric) == 1


class TestUsageCounterRepository:
    async def test_find_window_and_list_for_customer(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        await repos.usage_counters.create(
            UsageCounter(
                organization_id=organization_id,
                customer_id=customer.id,
                metric_key="api_calls",
                period_start=NOW,
                period_end=NOW + timedelta(days=1),
            )
        )
        found = await repos.usage_counters.find_window(
            customer.id, metric_key="api_calls", period_start=NOW
        )
        assert found is not None
        for_customer = await repos.usage_counters.list_for_customer(customer.id)
        assert len(for_customer) == 1

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        assert (
            await repos.usage_counters.find_window(
                customer.id, metric_key="api_calls", period_start=NOW
            )
            is None
        )


class TestQuotaRepository:
    async def test_list_for_customer_and_find_by_metric(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        await repos.quotas.create(
            Quota(
                organization_id=organization_id,
                customer_id=customer.id,
                metric_key="seats",
                limit_value=10.0,
                limit_kind=QuotaLimitKind.HARD,
                period=QuotaPeriod.MONTHLY,
            )
        )
        found = await repos.quotas.list_for_customer(customer.id)
        assert len(found) == 1
        by_metric = await repos.quotas.find_by_metric(customer.id, metric_key="seats")
        assert by_metric is not None
        recent = await repos.quotas.list_recent(organization_id)
        assert len(recent) == 1
        ids = await repos.quotas.list_organization_ids()
        assert organization_id in ids


class TestQuotaUsageRepository:
    async def test_find_window_and_list_for_quota(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        quota = await repos.quotas.create(
            Quota(
                organization_id=organization_id,
                customer_id=customer.id,
                metric_key="seats",
                limit_value=10.0,
                limit_kind=QuotaLimitKind.HARD,
                period=QuotaPeriod.MONTHLY,
            )
        )
        await repos.quota_usage.create(
            QuotaUsage(
                organization_id=organization_id,
                quota_id=quota.id,
                period_start=NOW,
                period_end=NOW + timedelta(days=30),
            )
        )
        found = await repos.quota_usage.find_window(quota.id, period_start=NOW)
        assert found is not None
        for_quota = await repos.quota_usage.list_for_quota(quota.id)
        assert len(for_quota) == 1


class TestBillingAccountRepository:
    async def test_find_for_customer_and_require_in_org(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        created = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        found = await repos.billing_accounts.find_for_customer(customer.id)
        assert found is not None and found.id == created.id
        required = await repos.billing_accounts.require_in_org(organization_id, created.id)
        assert required.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.billing_accounts.require_in_org(organization_id, uuid4())


class TestPaymentMethodRepository:
    async def test_list_for_billing_account_and_find_default(
        self, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        default_method = PaymentMethod(
            organization_id=organization_id,
            billing_account_id=account.id,
            method_type=PaymentMethodType.CREDIT_CARD,
            is_default=True,
        )
        await repos.payment_methods.create(default_method)
        found = await repos.payment_methods.list_for_billing_account(account.id)
        assert len(found) == 1
        default = await repos.payment_methods.find_default(account.id)
        assert default is not None and default.is_default


class TestPaymentTransactionRepository:
    async def test_list_recent_by_status_and_organization_ids(
        self, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        await repos.payment_transactions.create(
            PaymentTransaction(
                organization_id=organization_id,
                billing_account_id=account.id,
                amount=50.0,
                status=PaymentStatus.SUCCEEDED,
            )
        )
        for_account = await repos.payment_transactions.list_for_billing_account(account.id)
        assert len(for_account) == 1
        recent = await repos.payment_transactions.list_recent(
            organization_id, status=PaymentStatus.SUCCEEDED
        )
        assert len(recent) == 1
        by_status = await repos.payment_transactions.list_by_status(
            organization_id, status=PaymentStatus.SUCCEEDED
        )
        assert len(by_status) == 1
        ids = await repos.payment_transactions.list_organization_ids()
        assert organization_id in ids


class TestInvoiceRepository:
    async def test_require_in_org_and_list(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        created = await repos.invoices.create(
            Invoice(
                organization_id=organization_id,
                billing_account_id=account.id,
                invoice_number="INV-001",
                status=InvoiceStatus.ISSUED,
                issued_at=NOW,
            )
        )
        found = await repos.invoices.require_in_org(organization_id, created.id)
        assert found.id == created.id
        recent = await repos.invoices.list_recent(organization_id, status=InvoiceStatus.ISSUED)
        assert len(recent) == 1
        by_status = await repos.invoices.list_by_status(
            organization_id, status=InvoiceStatus.ISSUED
        )
        assert len(by_status) == 1
        ids = await repos.invoices.list_organization_ids()
        assert organization_id in ids
        for_subscription = await repos.invoices.list_for_subscription(uuid4())
        assert for_subscription == []

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.invoices.require_in_org(organization_id, uuid4())


class TestInvoiceItemRepository:
    async def test_list_for_invoice(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        invoice = await repos.invoices.create(
            Invoice(
                organization_id=organization_id,
                billing_account_id=account.id,
                invoice_number="INV-002",
                status=InvoiceStatus.DRAFT,
            )
        )
        await repos.invoice_items.create(
            InvoiceItem(
                organization_id=organization_id,
                invoice_id=invoice.id,
                description="Pro plan",
                quantity=1.0,
                unit_price=100.0,
                amount=100.0,
            )
        )
        found = await repos.invoice_items.list_for_invoice(invoice.id)
        assert len(found) == 1


class TestCreditRepository:
    async def test_list_for_billing_account(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        await repos.credits.create(
            Credit(organization_id=organization_id, billing_account_id=account.id, amount=25.0)
        )
        found = await repos.credits.list_for_billing_account(account.id)
        assert len(found) == 1


class TestDiscountRepository:
    async def test_list_enabled(self, repos, organization_id: UUID) -> None:
        await repos.discounts.create(
            Discount(
                organization_id=organization_id,
                name="Launch Discount",
                discount_type=DiscountType.PERCENTAGE,
                value=10.0,
            )
        )
        disabled = Discount(
            organization_id=organization_id, name="Old", discount_type=DiscountType.FIXED, value=5.0
        )
        disabled.is_enabled = False
        await repos.discounts.create(disabled)
        found = await repos.discounts.list_enabled(organization_id)
        assert len(found) == 1


class TestPromotionRepository:
    async def test_find_by_code(self, repos, organization_id: UUID) -> None:
        discount = await repos.discounts.create(
            Discount(
                organization_id=organization_id,
                name="Launch Discount",
                discount_type=DiscountType.PERCENTAGE,
                value=10.0,
            )
        )
        await repos.promotions.create(
            Promotion(organization_id=organization_id, code="LAUNCH10", discount_id=discount.id)
        )
        found = await repos.promotions.find_by_code(organization_id, code="LAUNCH10")
        assert found is not None


class TestMarketplaceSubscriptionRepository:
    async def test_list_for_customer(self, repos, organization_id: UUID) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.marketplace_subscriptions.create(
            MarketplaceSubscription(
                organization_id=organization_id,
                customer_id=customer.id,
                marketplace_ref="aws-mp-1",
                plan_id=plan.id,
                status=MarketplaceSubscriptionStatus.ACTIVE,
            )
        )
        found = await repos.marketplace_subscriptions.list_for_customer(customer.id)
        assert len(found) == 1


class TestBillingStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            BillingStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=NOW)
        assert found is not None
        in_range = await repos.statistics.list_range(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(in_range) == 1

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.statistics.find_window(organization_id, window_start=NOW) is None


class TestBillingReportRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.reports.create(
            BillingReport(
                organization_id=organization_id,
                kind=ReportKind.REVENUE,
                report_format=ReportFormat.JSON,
                title="Revenue Report",
                status=ReportStatus.COMPLETED,
            )
        )
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1
        by_kind = await repos.reports.list_recent(organization_id, kind=ReportKind.REVENUE)
        assert len(by_kind) == 1


class TestBillingAuditRepository:
    async def test_list_recent_and_for_entity(self, repos, organization_id: UUID) -> None:
        entity_id = uuid4()
        await repos.audit.create(
            BillingAudit(
                organization_id=organization_id,
                action=AuditAction.LICENSE_CREATED,
                entity_type="license",
                entity_id=entity_id,
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1
        for_entity = await repos.audit.list_for_entity("license", entity_id)
        assert len(for_entity) == 1

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            BillingAudit(
                organization_id=organization_id,
                action=AuditAction.LICENSE_CREATED,
                entity_type="license",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
