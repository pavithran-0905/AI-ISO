"""Quota creation, consumption, and period reset.

There is no ``POST`` route for ``api_quotas`` either -- a quota is
provisioned administratively (or, in tests, directly through this
service) when a developer subscribes to a plan, and only ever read
over HTTP via ``GET /quotas``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import QuotaExceededEvent
from app.models.enums import QuotaResetPolicy, QuotaType
from app.models.usage import ApiQuota
from app.quotas.engine import compute_period_window, is_quota_exceeded
from app.repositories.usage import ApiQuotaRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "public-api-platform"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class QuotaService:
    def __init__(
        self, repo: ApiQuotaRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def provision(
        self,
        organization_id: UUID,
        *,
        developer_account_id: UUID,
        quota_type: QuotaType,
        limit_value: int,
        reset_policy: QuotaResetPolicy,
        now: datetime,
    ) -> ApiQuota:
        period_start, period_end = compute_period_window(reset_policy, now=now)
        return await self._repo.create(
            ApiQuota(
                organization_id=organization_id,
                developer_account_id=developer_account_id,
                quota_type=quota_type,
                limit_value=limit_value,
                reset_policy=reset_policy,
                period_start=period_start,
                period_end=period_end,
            )
        )

    async def consume(self, quota: ApiQuota, *, amount: int = 1) -> ApiQuota:
        """Record *amount* of consumption against *quota*, publishing
        ``QuotaExceeded`` the moment it first crosses its own limit --
        never repeatedly for calls already past the limit."""
        was_exceeded = is_quota_exceeded(used_value=quota.used_value, limit_value=quota.limit_value)
        quota.used_value += amount
        quota = await self._repo.update(quota)
        now_exceeded = is_quota_exceeded(used_value=quota.used_value, limit_value=quota.limit_value)
        if now_exceeded and not was_exceeded:
            await self._publish(
                QuotaExceededEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=quota.organization_id,
                    payload={
                        "developer_account_id": str(quota.developer_account_id),
                        "quota_type": (
                            quota.quota_type.value
                            if hasattr(quota.quota_type, "value")
                            else quota.quota_type
                        ),
                    },
                )
            )
        return quota

    async def reset_for_new_period(self, quota: ApiQuota, *, now: datetime) -> ApiQuota:
        period_start, period_end = compute_period_window(quota.reset_policy, now=now)
        quota.used_value = 0
        quota.period_start = period_start
        quota.period_end = period_end
        return await self._repo.update(quota)


__all__ = ["QuotaService"]
