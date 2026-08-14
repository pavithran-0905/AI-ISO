"""Statistics rollup: idempotent per-window aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.reporting import BillingStatistic
from app.repositories.reporting import BillingStatisticRepository


class StatisticsService:
    """Rolls up one organization's billing counts for one window,
    idempotently."""

    def __init__(self, repo: BillingStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        mrr: float,
        arr: float,
        active_subscriptions: int,
        churned_subscriptions: int,
        invoices_generated: int,
        payments_received: int,
        payments_failed: int,
        quota_exceeded_count: int,
    ) -> BillingStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is None:
            existing = BillingStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.window_end = window_end
        existing.mrr = mrr
        existing.arr = arr
        existing.active_subscriptions = active_subscriptions
        existing.churned_subscriptions = churned_subscriptions
        existing.invoices_generated = invoices_generated
        existing.payments_received = payments_received
        existing.payments_failed = payments_failed
        existing.quota_exceeded_count = quota_exceeded_count
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
