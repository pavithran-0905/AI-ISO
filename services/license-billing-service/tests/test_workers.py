"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.billing import BillingAccount, Invoice
from app.models.customers import Customer
from app.models.enums import (
    BillingModel,
    CustomerType,
    InvoiceStatus,
    LicenseModel,
    LicenseStatus,
    QuotaLimitKind,
    QuotaPeriod,
    SubscriptionStatus,
)
from app.models.licenses import License
from app.models.subscriptions import Subscription, SubscriptionPlan
from app.models.usage import Quota
from app.workers.invoice_generation_sweep import InvoiceGenerationSweepWorker
from app.workers.license_expiry_sweep import LicenseExpirySweepWorker
from app.workers.quota_reset_sweep import QuotaResetSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.subscription_renewal_sweep import SubscriptionRenewalSweepWorker


def now() -> datetime:
    return datetime.now(UTC)


async def _noop_publish(event: object) -> None:
    pass


def _customer(organization_id: UUID, **kwargs: object) -> Customer:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "Acme",
        "customer_type": CustomerType.ORGANIZATION,
    }
    defaults.update(kwargs)
    return Customer(**defaults)


def _plan(organization_id: UUID, **kwargs: object) -> SubscriptionPlan:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "Pro",
        "billing_model": BillingModel.MONTHLY,
        "base_price": 100.0,
    }
    defaults.update(kwargs)
    return SubscriptionPlan(**defaults)


def _subscription(
    organization_id: UUID, customer_id: UUID, plan_id: UUID, **kwargs: object
) -> Subscription:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "customer_id": customer_id,
        "plan_id": plan_id,
        "status": SubscriptionStatus.ACTIVE,
        "start_at": now() - timedelta(days=1),
        "current_period_start": now() - timedelta(days=1),
        "current_period_end": now() + timedelta(days=29),
    }
    defaults.update(kwargs)
    return Subscription(**defaults)


def _license(organization_id: UUID, customer_id: UUID, **kwargs: object) -> License:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "customer_id": customer_id,
        "license_model": LicenseModel.SAAS,
        "status": LicenseStatus.ISSUED,
        "issued_at": now() - timedelta(days=1),
    }
    defaults.update(kwargs)
    return License(**defaults)


class TestSubscriptionRenewalSweepWorker:
    async def test_tick_notifies_trial_expiring(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(
            _subscription(
                organization_id,
                customer.id,
                plan.id,
                status=SubscriptionStatus.TRIAL,
                current_period_end=now() + timedelta(days=1),
            )
        )
        worker = SubscriptionRenewalSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            grace_period_days=7,
            renewal_reminder_days_before=3,
        )
        checked = await worker.tick()
        assert checked == 1
        assert any(name == "notify_trial_expiring" for name, _ in notifier.calls)

    async def test_tick_expires_subscription_past_grace_period(
        self, db_session_factory, db_session, repos, organization_id: UUID, notifier
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        subscription = await repos.subscriptions.create(
            _subscription(
                organization_id,
                customer.id,
                plan.id,
                status=SubscriptionStatus.ACTIVE,
                current_period_end=now() - timedelta(days=10),
            )
        )
        worker = SubscriptionRenewalSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            grace_period_days=7,
            renewal_reminder_days_before=14,
        )
        await worker.tick()

        await db_session.refresh(subscription)
        assert subscription.status == SubscriptionStatus.EXPIRED

    async def test_tick_notifies_renewal_reminder_within_window(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(
            _subscription(
                organization_id,
                customer.id,
                plan.id,
                status=SubscriptionStatus.ACTIVE,
                current_period_end=now() + timedelta(days=5),
            )
        )
        worker = SubscriptionRenewalSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            grace_period_days=7,
            renewal_reminder_days_before=14,
        )
        await worker.tick()
        assert any(name == "notify_renewal_reminder" for name, _ in notifier.calls)

    async def test_tick_no_organizations_checks_nothing(self, db_session_factory, notifier) -> None:
        worker = SubscriptionRenewalSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            grace_period_days=7,
            renewal_reminder_days_before=14,
        )
        assert await worker.tick() == 0


class TestLicenseExpirySweepWorker:
    async def test_tick_expires_license_past_expiry_and_notifies(
        self, db_session_factory, db_session, repos, organization_id: UUID, notifier
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(
            _license(organization_id, customer.id, expires_at=now() - timedelta(days=1))
        )
        worker = LicenseExpirySweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            reminder_days_before=14,
        )
        checked = await worker.tick()
        assert checked == 1

        await db_session.refresh(license_row)
        assert license_row.status == LicenseStatus.EXPIRED
        assert any(name == "notify_license_expired" for name, _ in notifier.calls)

    async def test_tick_leaves_unexpired_license_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID, notifier
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(
            _license(organization_id, customer.id, expires_at=now() + timedelta(days=365))
        )
        worker = LicenseExpirySweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            reminder_days_before=14,
        )
        await worker.tick()

        await db_session.refresh(license_row)
        assert license_row.status == LicenseStatus.ISSUED

    async def test_tick_perpetual_license_never_expires(
        self, db_session_factory, db_session, repos, organization_id: UUID, notifier
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        license_row = await repos.licenses.create(
            _license(organization_id, customer.id, expires_at=None)
        )
        worker = LicenseExpirySweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            reminder_days_before=14,
        )
        await worker.tick()

        await db_session.refresh(license_row)
        assert license_row.status == LicenseStatus.ISSUED

    async def test_tick_no_organizations_checks_nothing(self, db_session_factory, notifier) -> None:
        worker = LicenseExpirySweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            reminder_days_before=14,
        )
        assert await worker.tick() == 0


class TestQuotaResetSweepWorker:
    async def test_tick_opens_current_window(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
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
        worker = QuotaResetSweepWorker(db_session_factory)
        opened = await worker.tick()
        assert opened == 1

        from app.quotas.engine import compute_period_window

        period_start, _ = compute_period_window(quota.period, now=now())
        window = await repos.quota_usage.find_window(quota.id, period_start=period_start)
        assert window is not None
        assert window.used_value == 0.0

    async def test_tick_is_idempotent(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
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
        worker = QuotaResetSweepWorker(db_session_factory)
        first = await worker.tick()
        second = await worker.tick()
        assert first == 1
        assert second == 0

    async def test_tick_no_organizations_opens_nothing(self, db_session_factory) -> None:
        worker = QuotaResetSweepWorker(db_session_factory)
        assert await worker.tick() == 0


class TestInvoiceGenerationSweepWorker:
    async def test_tick_generates_invoice_for_active_subscription(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        subscription = await repos.subscriptions.create(
            _subscription(organization_id, customer.id, plan.id)
        )
        worker = InvoiceGenerationSweepWorker(
            db_session_factory, publish_event=_noop_publish, due_days=30
        )
        generated = await worker.tick()
        assert generated == 1

        invoices = await repos.invoices.list_for_subscription(subscription.id)
        assert len(invoices) == 1
        assert invoices[0].total_amount == 100.0

    async def test_tick_does_not_double_invoice_same_period(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        await repos.subscriptions.create(_subscription(organization_id, customer.id, plan.id))
        worker = InvoiceGenerationSweepWorker(
            db_session_factory, publish_event=_noop_publish, due_days=30
        )
        first = await worker.tick()
        second = await worker.tick()
        assert first == 1
        assert second == 0

    async def test_tick_skips_subscription_without_billing_account(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(_subscription(organization_id, customer.id, plan.id))
        worker = InvoiceGenerationSweepWorker(
            db_session_factory, publish_event=_noop_publish, due_days=30
        )
        assert await worker.tick() == 0

    async def test_tick_marks_overdue_invoices(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        invoice = await repos.invoices.create(
            Invoice(
                organization_id=organization_id,
                billing_account_id=account.id,
                invoice_number="INV-OVERDUE-1",
                status=InvoiceStatus.ISSUED,
                issued_at=now() - timedelta(days=60),
                due_at=now() - timedelta(days=1),
            )
        )
        worker = InvoiceGenerationSweepWorker(
            db_session_factory, publish_event=_noop_publish, due_days=30
        )
        await worker.tick()

        await db_session.refresh(invoice)
        assert invoice.status == InvoiceStatus.OVERDUE

    async def test_tick_no_organizations_generates_nothing(self, db_session_factory) -> None:
        worker = InvoiceGenerationSweepWorker(
            db_session_factory, publish_event=_noop_publish, due_days=30
        )
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        customer = await repos.customers.create(_customer(organization_id))
        plan = await repos.plans.create(_plan(organization_id))
        await repos.subscriptions.create(_subscription(organization_id, customer.id, plan.id))

        worker = StatisticsRollupWorker(db_session_factory)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second == 1

        window_end = now().replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        statistic = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert statistic is not None
        assert statistic.mrr == 100.0
        assert statistic.arr == 1200.0
        assert statistic.active_subscriptions == 1

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
