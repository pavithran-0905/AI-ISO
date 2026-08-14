"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.events.domain_events import (
    CustomerCreatedEvent,
    InvoiceGeneratedEvent,
    LicenseActivatedEvent,
    LicenseRevokedEvent,
    MarketplacePurchaseCompletedEvent,
    PaymentFailedEvent,
    PaymentReceivedEvent,
    QuotaExceededEvent,
    SubscriptionCreatedEvent,
    SubscriptionExpiredEvent,
    SubscriptionRenewedEvent,
)
from app.models.enums import (
    BillingModel,
    ContractStatus,
    CustomerType,
    DiscountType,
    LicenseModel,
    LicenseStatus,
    PaymentMethodType,
    PaymentStatus,
    QuotaLimitKind,
    QuotaPeriod,
    ReportFormat,
    ReportKind,
    SubscriptionStatus,
)
from app.services.audit import AuditService
from app.services.billing_accounts import BillingAccountService, PaymentMethodService
from app.services.contracts import ContractService
from app.services.customers import CustomerAccountService, CustomerService
from app.services.entitlements import LicenseEntitlementService, SubscriptionFeatureService
from app.services.invoices import InvoiceItemInput, InvoiceService
from app.services.licenses import LicenseService, SeatLimitReachedError
from app.services.licenses import TransitionRefusedError as LicenseTransitionRefusedError
from app.services.marketplace import MarketplaceSubscriptionService
from app.services.offline import OfflineLicenseService
from app.services.payments import PaymentService
from app.services.pricing import DiscountService, PromotionRefusedError, PromotionService
from app.services.quotas import QuotaService
from app.services.reports import ReportService
from app.services.statistics import StatisticsService
from app.services.subscriptions import (
    SubscriptionPlanService,
    SubscriptionService,
    TransitionRefusedError,
)
from app.services.usage import UsageService

NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _make_customer(repos, organization_id):
    from app.models.customers import Customer

    return await repos.customers.create(
        Customer(
            organization_id=organization_id, name="Acme", customer_type=CustomerType.ORGANIZATION
        )
    )


async def _make_plan(repos, organization_id):
    return await SubscriptionPlanService(repos.plans).create_plan(
        organization_id, name="Pro", billing_model=BillingModel.MONTHLY, base_price=100.0
    )


class TestCustomerService:
    async def test_create_customer_publishes_event(self, repos, organization_id, publisher) -> None:
        service = CustomerService(repos.customers, publish=publisher)
        customer = await service.create_customer(
            organization_id, name="Acme", customer_type=CustomerType.ORGANIZATION
        )
        assert customer.id is not None
        assert publisher.names() == [CustomerCreatedEvent.event_name]


class TestCustomerAccountService:
    async def test_create_suspend_close(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        service = CustomerAccountService(repos.customer_accounts)
        account = await service.create_account(
            organization_id, customer_id=customer.id, external_account_ref="ext-1"
        )
        suspended = await service.suspend(account)
        assert suspended.account_status.value == "suspended"
        closed = await service.close(suspended)
        assert closed.account_status.value == "closed"


class TestSubscriptionPlanService:
    async def test_create_plan(self, repos, organization_id) -> None:
        plan = await _make_plan(repos, organization_id)
        assert plan.base_price == 100.0


class TestSubscriptionService:
    async def test_create_subscription_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        customer = await _make_customer(repos, organization_id)
        plan = await _make_plan(repos, organization_id)
        service = SubscriptionService(repos.subscriptions, publish=publisher)
        subscription = await service.create_subscription(
            organization_id,
            customer_id=customer.id,
            plan_id=plan.id,
            start_at=NOW,
            current_period_end=NOW + timedelta(days=30),
            actor_id="tester",
            now=NOW,
        )
        assert subscription.status == SubscriptionStatus.TRIAL
        assert publisher.names() == [SubscriptionCreatedEvent.event_name]

    async def test_transition_to_active(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        plan = await _make_plan(repos, organization_id)
        service = SubscriptionService(repos.subscriptions, publish=publisher)
        subscription = await service.create_subscription(
            organization_id,
            customer_id=customer.id,
            plan_id=plan.id,
            start_at=NOW,
            current_period_end=NOW + timedelta(days=30),
            actor_id=None,
            now=NOW,
        )
        activated = await service.transition(
            subscription, target=SubscriptionStatus.ACTIVE, actor_id=None, now=NOW
        )
        assert activated.status == SubscriptionStatus.ACTIVE

    async def test_transition_to_expired_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        customer = await _make_customer(repos, organization_id)
        plan = await _make_plan(repos, organization_id)
        service = SubscriptionService(repos.subscriptions, publish=publisher)
        subscription = await service.create_subscription(
            organization_id,
            customer_id=customer.id,
            plan_id=plan.id,
            start_at=NOW,
            current_period_end=NOW + timedelta(days=30),
            actor_id=None,
            now=NOW,
        )
        await service.transition(
            subscription, target=SubscriptionStatus.EXPIRED, actor_id=None, now=NOW
        )
        assert SubscriptionExpiredEvent.event_name in publisher.names()

    async def test_invalid_transition_raises(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        plan = await _make_plan(repos, organization_id)
        service = SubscriptionService(repos.subscriptions, publish=publisher)
        subscription = await service.create_subscription(
            organization_id,
            customer_id=customer.id,
            plan_id=plan.id,
            start_at=NOW,
            current_period_end=NOW + timedelta(days=30),
            actor_id=None,
            now=NOW,
        )
        with pytest.raises(TransitionRefusedError):
            await service.transition(
                subscription, target=SubscriptionStatus.SUSPENDED, actor_id=None, now=NOW
            )

    async def test_renew_publishes_event(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        plan = await _make_plan(repos, organization_id)
        service = SubscriptionService(repos.subscriptions, publish=publisher)
        subscription = await service.create_subscription(
            organization_id,
            customer_id=customer.id,
            plan_id=plan.id,
            start_at=NOW,
            current_period_end=NOW + timedelta(days=30),
            actor_id=None,
            now=NOW,
        )
        renewed = await service.renew(
            subscription, new_period_end=NOW + timedelta(days=60), now=NOW
        )
        assert renewed.status == SubscriptionStatus.ACTIVE
        assert SubscriptionRenewedEvent.event_name in publisher.names()


class TestLicenseService:
    async def test_issue_license(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        service = LicenseService(repos.licenses, repos.license_activations)
        license_row = await service.issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=1,
            actor_id="tester",
            now=NOW,
        )
        assert license_row.status == LicenseStatus.ISSUED

    async def test_activate_seat_publishes_event(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        service = LicenseService(repos.licenses, repos.license_activations, publish=publisher)
        license_row = await service.issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=1,
            actor_id=None,
            now=NOW,
        )
        activation = await service.activate_seat(
            license_row, activation_ref="device-1", actor_id=None, now=NOW
        )
        assert activation.id is not None
        assert LicenseActivatedEvent.event_name in publisher.names()

    async def test_activate_seat_past_limit_raises(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        service = LicenseService(repos.licenses, repos.license_activations, publish=publisher)
        license_row = await service.issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=1,
            actor_id=None,
            now=NOW,
        )
        await service.activate_seat(license_row, activation_ref="device-1", actor_id=None, now=NOW)
        with pytest.raises(SeatLimitReachedError):
            await service.activate_seat(
                license_row, activation_ref="device-2", actor_id=None, now=NOW
            )

    async def test_transition_to_revoked_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        customer = await _make_customer(repos, organization_id)
        service = LicenseService(repos.licenses, repos.license_activations, publish=publisher)
        license_row = await service.issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=None,
            actor_id=None,
            now=NOW,
        )
        revoked = await service.transition(
            license_row, target=LicenseStatus.REVOKED, actor_id=None, now=NOW
        )
        assert revoked.status == LicenseStatus.REVOKED
        assert LicenseRevokedEvent.event_name in publisher.names()

    async def test_invalid_transition_raises(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        service = LicenseService(repos.licenses, repos.license_activations)
        license_row = await service.issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=None,
            actor_id=None,
            now=NOW,
        )
        revoked = await service.transition(
            license_row, target=LicenseStatus.REVOKED, actor_id=None, now=NOW
        )
        with pytest.raises(LicenseTransitionRefusedError):
            await service.transition(revoked, target=LicenseStatus.ACTIVE, actor_id=None, now=NOW)

    async def test_deactivate_seat(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        service = LicenseService(repos.licenses, repos.license_activations)
        license_row = await service.issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=None,
            actor_id=None,
            now=NOW,
        )
        activation = await service.activate_seat(
            license_row, activation_ref="device-1", actor_id=None, now=NOW
        )
        deactivated = await service.deactivate_seat(activation, now=NOW)
        assert deactivated.is_enabled is False


class TestContractService:
    async def test_create_approve_reject_terminate(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        audit = AuditService(repos.audit)
        service = ContractService(repos.contracts, audit=audit)
        contract = await service.create_contract(
            organization_id,
            customer_id=customer.id,
            name="Enterprise Deal",
            terms={},
            actor_id="tester",
            now=NOW,
        )
        assert contract.status == ContractStatus.DRAFT
        approved = await service.approve(contract, now=NOW)
        assert approved.status == ContractStatus.ACTIVE

        rejected_service = ContractService(repos.contracts)
        other = await rejected_service.create_contract(
            organization_id,
            customer_id=customer.id,
            name="Other Deal",
            terms={},
            actor_id=None,
            now=NOW,
        )
        rejected = await rejected_service.reject(other)
        assert rejected.approval_status.value == "rejected"
        terminated = await rejected_service.terminate(approved)
        assert terminated.status == ContractStatus.TERMINATED


class TestUsageService:
    async def test_record_and_roll_up_window(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        service = UsageService(repos.usage_records, repos.usage_counters)
        await service.record(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            metric_key="api_calls",
            quantity=5.0,
            now=NOW,
        )
        await service.record(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            metric_key="api_calls",
            quantity=3.0,
            now=NOW,
        )
        counter = await service.roll_up_window(
            organization_id,
            customer_id=customer.id,
            metric_key="api_calls",
            period_start=NOW,
            period_end=NOW + timedelta(days=1),
            quantities=[5.0, 3.0],
        )
        assert counter.total_quantity == 8.0

        # idempotent: a second rollup for the same window updates, not duplicates
        counter2 = await service.roll_up_window(
            organization_id,
            customer_id=customer.id,
            metric_key="api_calls",
            period_start=NOW,
            period_end=NOW + timedelta(days=1),
            quantities=[5.0, 3.0, 2.0],
        )
        assert counter2.id == counter.id
        assert counter2.total_quantity == 10.0


class TestQuotaService:
    async def test_create_quota_and_admit_request(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        service = QuotaService(repos.quotas, repos.quota_usage, publish=publisher)
        quota = await service.create_quota(
            organization_id,
            customer_id=customer.id,
            metric_key="seats",
            limit_value=10.0,
            limit_kind=QuotaLimitKind.HARD,
            period=QuotaPeriod.MONTHLY,
        )
        window = await service.request(
            quota, requested_value=5.0, period_start=NOW, period_end=NOW + timedelta(days=30)
        )
        assert window.used_value == 5.0

    async def test_hard_quota_refusal_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        customer = await _make_customer(repos, organization_id)
        service = QuotaService(repos.quotas, repos.quota_usage, publish=publisher)
        quota = await service.create_quota(
            organization_id,
            customer_id=customer.id,
            metric_key="seats",
            limit_value=5.0,
            limit_kind=QuotaLimitKind.HARD,
            period=QuotaPeriod.MONTHLY,
        )
        window = await service.request(
            quota, requested_value=10.0, period_start=NOW, period_end=NOW + timedelta(days=30)
        )
        assert window.used_value == 0.0
        assert QuotaExceededEvent.event_name in publisher.names()

    async def test_classify(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        service = QuotaService(repos.quotas, repos.quota_usage)
        quota = await service.create_quota(
            organization_id,
            customer_id=customer.id,
            metric_key="seats",
            limit_value=10.0,
            limit_kind=QuotaLimitKind.SOFT,
            period=QuotaPeriod.MONTHLY,
        )
        assert service.classify(quota, used_value=1.0, warning_fraction=0.8) == "ok"


class TestBillingAccountService:
    async def test_create_account(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        assert account.currency == "USD"


class TestPaymentMethodService:
    async def test_add_method_and_default_swap(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        service = PaymentMethodService(repos.payment_methods)
        first = await service.add_method(
            organization_id,
            billing_account_id=account.id,
            method_type=PaymentMethodType.CREDIT_CARD,
            reference="tok_1",
            is_default=True,
        )
        second = await service.add_method(
            organization_id,
            billing_account_id=account.id,
            method_type=PaymentMethodType.BANK_TRANSFER,
            reference="tok_2",
            is_default=True,
        )
        assert second.is_default
        refreshed_first = await repos.payment_methods.require_by_id(first.id)
        assert refreshed_first.is_default is False


class TestPaymentService:
    async def test_mark_succeeded_publishes_event(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        service = PaymentService(
            repos.payment_transactions, publish=publisher, audit=AuditService(repos.audit)
        )
        transaction = await service.record_attempt(
            organization_id,
            billing_account_id=account.id,
            payment_method_id=None,
            invoice_id=None,
            amount=100.0,
            currency="USD",
        )
        assert transaction.status == PaymentStatus.PENDING
        succeeded = await service.mark_succeeded(transaction, now=NOW)
        assert succeeded.status == PaymentStatus.SUCCEEDED
        assert PaymentReceivedEvent.event_name in publisher.names()

    async def test_mark_failed_publishes_event(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        service = PaymentService(repos.payment_transactions, publish=publisher)
        transaction = await service.record_attempt(
            organization_id,
            billing_account_id=account.id,
            payment_method_id=None,
            invoice_id=None,
            amount=100.0,
            currency="USD",
        )
        failed = await service.mark_failed(transaction, now=NOW)
        assert failed.status == PaymentStatus.FAILED
        assert PaymentFailedEvent.event_name in publisher.names()

    async def test_prepare_retry(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        service = PaymentService(repos.payment_transactions)
        transaction = await service.record_attempt(
            organization_id,
            billing_account_id=account.id,
            payment_method_id=None,
            invoice_id=None,
            amount=100.0,
            currency="USD",
        )
        failed = await service.mark_failed(transaction, now=NOW)
        decision = await service.prepare_retry(failed, max_attempts=3)
        assert decision.should_retry
        assert failed.status == PaymentStatus.PENDING
        assert failed.attempt_count == 2


class TestInvoiceService:
    async def test_generate_publishes_event(self, repos, organization_id, publisher) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        service = InvoiceService(repos.invoices, repos.invoice_items, publish=publisher)
        invoice = await service.generate(
            organization_id,
            billing_account_id=account.id,
            subscription_id=None,
            invoice_number="INV-100",
            items=[InvoiceItemInput(description="Pro plan", quantity=1.0, unit_price=100.0)],
            currency="USD",
            due_days=30,
            actor_id="tester",
            now=NOW,
        )
        assert invoice.total_amount == 100.0
        assert InvoiceGeneratedEvent.event_name in publisher.names()

    async def test_mark_paid_overdue_void(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        account = await BillingAccountService(repos.billing_accounts).create_account(
            organization_id, customer_id=customer.id
        )
        service = InvoiceService(repos.invoices, repos.invoice_items)
        invoice = await service.generate(
            organization_id,
            billing_account_id=account.id,
            subscription_id=None,
            invoice_number="INV-101",
            items=[InvoiceItemInput(description="Pro plan", quantity=1.0, unit_price=100.0)],
            currency="USD",
            due_days=30,
            actor_id=None,
            now=NOW,
        )
        paid = await service.mark_paid(invoice)
        assert paid.status.value == "paid"

        invoice2 = await service.generate(
            organization_id,
            billing_account_id=account.id,
            subscription_id=None,
            invoice_number="INV-102",
            items=[InvoiceItemInput(description="Pro plan", quantity=1.0, unit_price=100.0)],
            currency="USD",
            due_days=30,
            actor_id=None,
            now=NOW,
        )
        overdue = await service.mark_overdue(invoice2)
        assert overdue.status.value == "overdue"
        voided = await service.void(overdue)
        assert voided.status.value == "void"


class TestDiscountService:
    async def test_create_and_disable(self, repos, organization_id) -> None:
        service = DiscountService(repos.discounts)
        discount = await service.create_discount(
            organization_id, name="Launch", discount_type=DiscountType.PERCENTAGE, value=10.0
        )
        disabled = await service.disable(discount)
        assert disabled.is_enabled is False


class TestPromotionService:
    async def test_create_and_redeem(self, repos, organization_id) -> None:
        discount = await DiscountService(repos.discounts).create_discount(
            organization_id, name="Launch", discount_type=DiscountType.PERCENTAGE, value=10.0
        )
        service = PromotionService(repos.promotions)
        promotion = await service.create_promotion(
            organization_id,
            code="LAUNCH10",
            discount_id=discount.id,
            starts_at=None,
            ends_at=None,
            max_redemptions=1,
        )
        redeemed = await service.redeem(promotion, now=NOW)
        assert redeemed.redemption_count == 1

    async def test_redeem_past_limit_raises(self, repos, organization_id) -> None:
        discount = await DiscountService(repos.discounts).create_discount(
            organization_id, name="Launch", discount_type=DiscountType.PERCENTAGE, value=10.0
        )
        service = PromotionService(repos.promotions)
        promotion = await service.create_promotion(
            organization_id,
            code="ONE-USE",
            discount_id=discount.id,
            starts_at=None,
            ends_at=None,
            max_redemptions=1,
        )
        await service.redeem(promotion, now=NOW)
        with pytest.raises(PromotionRefusedError):
            await service.redeem(promotion, now=NOW)


class TestMarketplaceSubscriptionService:
    async def test_purchase_publishes_event_and_cancel(
        self, repos, organization_id, publisher
    ) -> None:
        customer = await _make_customer(repos, organization_id)
        plan = await _make_plan(repos, organization_id)
        service = MarketplaceSubscriptionService(repos.marketplace_subscriptions, publish=publisher)
        subscription = await service.purchase(
            organization_id, customer_id=customer.id, marketplace_ref="aws-mp-1", plan_id=plan.id
        )
        assert MarketplacePurchaseCompletedEvent.event_name in publisher.names()
        cancelled = await service.cancel(subscription)
        assert cancelled.status.value == "cancelled"


class TestStatisticsService:
    async def test_roll_up_window_is_idempotent(self, repos, organization_id) -> None:
        service = StatisticsService(repos.statistics)
        first = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            mrr=100.0,
            arr=1200.0,
            active_subscriptions=1,
            churned_subscriptions=0,
            invoices_generated=1,
            payments_received=1,
            payments_failed=0,
            quota_exceeded_count=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            mrr=200.0,
            arr=2400.0,
            active_subscriptions=2,
            churned_subscriptions=1,
            invoices_generated=2,
            payments_received=2,
            payments_failed=1,
            quota_exceeded_count=1,
        )
        assert second.id == first.id
        assert second.mrr == 200.0
        assert second.active_subscriptions == 2


class TestReportService:
    async def test_generate(self, repos, organization_id) -> None:
        report = await ReportService(repos.reports).generate(
            organization_id,
            kind=ReportKind.REVENUE,
            title="Q2 Revenue",
            report_format=ReportFormat.JSON,
            period_start=NOW,
            period_end=NOW + timedelta(days=30),
            content={"mrr": 1000.0},
            row_count=1,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"


class TestLicenseEntitlementService:
    async def test_grant_and_check(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        license_row = await LicenseService(repos.licenses, repos.license_activations).issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.SAAS,
            expires_at=None,
            seat_limit=None,
            actor_id=None,
            now=NOW,
        )
        service = LicenseEntitlementService(repos.license_entitlements)
        await service.grant(
            organization_id, license_id=license_row.id, feature_key="sso", limit_value=None
        )
        assert await service.check(license_row.id, feature_key="sso", current_usage=0) is True
        assert await service.check(license_row.id, feature_key="unknown", current_usage=0) is False


class TestSubscriptionFeatureService:
    async def test_grant_and_check(self, repos, organization_id) -> None:
        plan = await _make_plan(repos, organization_id)
        service = SubscriptionFeatureService(repos.plan_features)
        await service.grant(organization_id, plan_id=plan.id, feature_key="seats", limit_value=5)
        assert await service.check(plan.id, feature_key="seats", current_usage=4) is True
        assert await service.check(plan.id, feature_key="seats", current_usage=5) is False


class TestOfflineLicenseService:
    async def test_issue_validate_revoke(self, repos, organization_id) -> None:
        customer = await _make_customer(repos, organization_id)
        license_row = await LicenseService(repos.licenses, repos.license_activations).issue_license(
            organization_id,
            customer_id=customer.id,
            subscription_id=None,
            license_model=LicenseModel.OFFLINE,
            expires_at=None,
            seat_limit=None,
            actor_id=None,
            now=NOW,
        )
        service = OfflineLicenseService(repos.offline_licenses)
        content = b"license-file-bytes"
        offline_license = await service.issue(
            organization_id,
            license_id=license_row.id,
            file_content=content,
            expires_at=NOW + timedelta(days=365),
            now=NOW,
        )
        validation = await service.validate(offline_license, file_content=content, now=NOW)
        assert validation.is_valid

        tampered = await service.validate(offline_license, file_content=b"tampered", now=NOW)
        assert not tampered.is_valid

        revoked = await service.revoke(offline_license)
        assert revoked.is_revoked is True


class TestAuditService:
    async def test_record(self, repos, organization_id) -> None:
        from app.models.enums import AuditAction

        entry = await AuditService(repos.audit).record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="test",
            entity_id=None,
            occurred_at=NOW,
            summary="test entry",
        )
        assert entry.id is not None
        assert entry.succeeded is True
