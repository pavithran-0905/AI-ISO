"""Developer platform statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern ``services/sdk-cli-service`` and
``services/administration-portal-service`` established.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import DeveloperStatistic
from app.repositories.reporting import DeveloperStatisticRepository


class StatisticsService:
    def __init__(self, repo: DeveloperStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        api_call_count: int,
        registration_count: int,
        application_count: int,
        sdk_download_count: int,
        error_count: int,
        average_latency_ms: float,
    ) -> DeveloperStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.api_call_count = api_call_count
            existing.registration_count = registration_count
            existing.application_count = application_count
            existing.sdk_download_count = sdk_download_count
            existing.error_count = error_count
            existing.average_latency_ms = average_latency_ms
            return await self._repo.update(existing)
        return await self._repo.create(
            DeveloperStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                api_call_count=api_call_count,
                registration_count=registration_count,
                application_count=application_count,
                sdk_download_count=sdk_download_count,
                error_count=error_count,
                average_latency_ms=average_latency_ms,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[DeveloperStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
