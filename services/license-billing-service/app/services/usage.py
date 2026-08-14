"""Usage recording and idempotent per-window rollup.

Wires ``app.usage.engine``'s pure aggregation onto the repositories that
persist raw usage records and their window rollups.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.usage import UsageCounter, UsageRecord
from app.repositories.usage import UsageCounterRepository, UsageRecordRepository
from app.usage.engine import aggregate_quantities


class UsageService:
    def __init__(
        self, record_repo: UsageRecordRepository, counter_repo: UsageCounterRepository
    ) -> None:
        self._record_repo = record_repo
        self._counter_repo = counter_repo

    async def record(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        subscription_id: UUID | None,
        metric_key: str,
        quantity: float,
        now: datetime,
    ) -> UsageRecord:
        return await self._record_repo.create(
            UsageRecord(
                organization_id=organization_id,
                customer_id=customer_id,
                subscription_id=subscription_id,
                metric_key=metric_key,
                quantity=quantity,
                recorded_at=now,
            )
        )

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        metric_key: str,
        period_start: datetime,
        period_end: datetime,
        quantities: list[float],
    ) -> UsageCounter:
        """Idempotently roll every quantity in *quantities* up into one
        window counter."""
        existing = await self._counter_repo.find_window(
            customer_id, metric_key=metric_key, period_start=period_start
        )
        if existing is None:
            existing = UsageCounter(
                organization_id=organization_id,
                customer_id=customer_id,
                metric_key=metric_key,
                period_start=period_start,
                period_end=period_end,
            )
            existing = await self._counter_repo.create(existing)

        existing.period_end = period_end
        existing.total_quantity = aggregate_quantities(quantities)
        return await self._counter_repo.update(existing)


__all__ = ["UsageService"]
