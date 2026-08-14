"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

MRR/ARR and the quota-exceeded count are live snapshots at
``window_end`` -- they describe standing state, not events that
occurred during the window. Churn, invoices, and payments are counted
strictly within ``[window_start, window_end)``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.engine import compute_arr, normalize_to_monthly_recurring_revenue
from app.models.billing import Invoice, PaymentTransaction
from app.models.enums import PaymentStatus, SubscriptionStatus
from app.models.subscriptions import Subscription
from app.quotas.engine import QuotaStatus, classify_quota_status, compute_period_window
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_CHURNED_STATUSES = frozenset({SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED})


class StatisticsRollupWorker:
    """Recomputes every organization's revenue and billing statistics."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        window_hours: int = 1,
        quota_warning_fraction: float = 0.8,
    ) -> None:
        self._session_factory = session_factory
        self._window_hours = window_hours
        self._quota_warning_fraction = quota_warning_fraction

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Roll up the last completed window, returning how many
        organizations were rolled up."""
        window_end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=self._window_hours)
        rolled = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = StatisticsService(repos.statistics)

            for organization_id in await repos.subscriptions.list_organization_ids():
                active_subscriptions = await repos.subscriptions.list_by_status(
                    organization_id, status=SubscriptionStatus.ACTIVE
                )
                mrr = 0.0
                for subscription in active_subscriptions:
                    plan = await repos.plans.get_by_id(subscription.plan_id)
                    if plan is not None:
                        mrr += normalize_to_monthly_recurring_revenue(
                            plan.base_price, billing_model=plan.billing_model
                        )
                arr = compute_arr(mrr)

                churned_subscriptions = (
                    await session.execute(
                        select(func.count())
                        .select_from(Subscription)
                        .where(
                            Subscription.organization_id == organization_id,
                            Subscription.status.in_(_CHURNED_STATUSES),
                            Subscription.updated_at >= window_start,
                            Subscription.updated_at < window_end,
                        )
                    )
                ).scalar_one()

                invoices_generated = (
                    await session.execute(
                        select(func.count())
                        .select_from(Invoice)
                        .where(
                            Invoice.organization_id == organization_id,
                            Invoice.issued_at >= window_start,
                            Invoice.issued_at < window_end,
                        )
                    )
                ).scalar_one()

                payments_received = (
                    await session.execute(
                        select(func.count())
                        .select_from(PaymentTransaction)
                        .where(
                            PaymentTransaction.organization_id == organization_id,
                            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
                            PaymentTransaction.processed_at >= window_start,
                            PaymentTransaction.processed_at < window_end,
                        )
                    )
                ).scalar_one()

                payments_failed = (
                    await session.execute(
                        select(func.count())
                        .select_from(PaymentTransaction)
                        .where(
                            PaymentTransaction.organization_id == organization_id,
                            PaymentTransaction.status == PaymentStatus.FAILED,
                            PaymentTransaction.processed_at >= window_start,
                            PaymentTransaction.processed_at < window_end,
                        )
                    )
                ).scalar_one()

                quota_exceeded_count = 0
                for quota in await repos.quotas.list_recent(organization_id, limit=5000):
                    period_start, _ = compute_period_window(quota.period, now=window_end)
                    usage_window = await repos.quota_usage.find_window(
                        quota.id, period_start=period_start
                    )
                    if usage_window is None:
                        continue
                    status = classify_quota_status(
                        usage_window.used_value,
                        quota.limit_value,
                        warning_fraction=self._quota_warning_fraction,
                    )
                    if status == QuotaStatus.EXCEEDED:
                        quota_exceeded_count += 1

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    mrr=mrr,
                    arr=arr,
                    active_subscriptions=len(active_subscriptions),
                    churned_subscriptions=churned_subscriptions,
                    invoices_generated=invoices_generated,
                    payments_received=payments_received,
                    payments_failed=payments_failed,
                    quota_exceeded_count=quota_exceeded_count,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
