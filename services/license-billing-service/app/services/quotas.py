"""Quota definition and request admission control.

Wires ``app.quotas.engine``'s pure classification and admission check
onto the repositories that persist quota definitions and per-window
usage, publishing ``QuotaExceeded`` on a hard refusal.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import QuotaExceededEvent
from app.models.enums import QuotaLimitKind, QuotaPeriod
from app.models.usage import Quota, QuotaUsage
from app.quotas.engine import classify_quota_status, is_request_allowed
from app.repositories.usage import QuotaRepository, QuotaUsageRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class QuotaService:
    def __init__(
        self,
        quota_repo: QuotaRepository,
        usage_repo: QuotaUsageRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._quota_repo = quota_repo
        self._usage_repo = usage_repo
        self._publish = publish

    async def create_quota(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        metric_key: str,
        limit_value: float,
        limit_kind: QuotaLimitKind,
        period: QuotaPeriod,
        burst_limit: float | None = None,
    ) -> Quota:
        return await self._quota_repo.create(
            Quota(
                organization_id=organization_id,
                customer_id=customer_id,
                metric_key=metric_key,
                limit_value=limit_value,
                limit_kind=limit_kind,
                period=period,
                burst_limit=burst_limit,
            )
        )

    async def request(
        self,
        quota: Quota,
        *,
        requested_value: float,
        period_start: datetime,
        period_end: datetime,
    ) -> QuotaUsage:
        """Admit or refuse a request for *requested_value* more usage
        against *quota*, updating the window's used total and
        publishing ``QuotaExceeded`` on a hard refusal.

        A refused request never increments the usage total -- only an
        admitted request actually consumes quota.
        """
        window = await self._usage_repo.find_window(quota.id, period_start=period_start)
        if window is None:
            window = QuotaUsage(
                organization_id=quota.organization_id,
                quota_id=quota.id,
                period_start=period_start,
                period_end=period_end,
            )
            window = await self._usage_repo.create(window)

        allowed = is_request_allowed(
            window.used_value,
            requested_value,
            limit_value=quota.limit_value,
            limit_kind=quota.limit_kind,
            burst_limit=quota.burst_limit,
        )
        if not allowed:
            await self._publish(
                QuotaExceededEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=quota.organization_id,
                    payload={
                        "customer_id": str(quota.customer_id),
                        "quota_id": str(quota.id),
                        "metric_key": quota.metric_key,
                    },
                )
            )
            return window

        window.used_value += requested_value
        return await self._usage_repo.update(window)

    def classify(self, quota: Quota, *, used_value: float, warning_fraction: float) -> str:
        return classify_quota_status(
            used_value, quota.limit_value, warning_fraction=warning_fraction
        )


__all__ = ["QuotaService"]
