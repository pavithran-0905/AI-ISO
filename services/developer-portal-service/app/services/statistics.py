"""Portal statistics rollup and retrieval.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it --
the same pattern every prior rollup worker in this codebase uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.reporting import PortalStatistic
from app.repositories.reporting import PortalStatisticRepository


class StatisticsService:
    def __init__(self, repo: PortalStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        portal_visit_count: int,
        documentation_view_count: int,
        sdk_download_count: int,
        search_query_count: int,
        tutorial_completion_count: int,
        plugin_publication_count: int,
        community_activity_count: int,
        ai_assistant_usage_count: int,
    ) -> PortalStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is not None:
            existing.window_end = window_end
            existing.portal_visit_count = portal_visit_count
            existing.documentation_view_count = documentation_view_count
            existing.sdk_download_count = sdk_download_count
            existing.search_query_count = search_query_count
            existing.tutorial_completion_count = tutorial_completion_count
            existing.plugin_publication_count = plugin_publication_count
            existing.community_activity_count = community_activity_count
            existing.ai_assistant_usage_count = ai_assistant_usage_count
            return await self._repo.update(existing)
        return await self._repo.create(
            PortalStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                portal_visit_count=portal_visit_count,
                documentation_view_count=documentation_view_count,
                sdk_download_count=sdk_download_count,
                search_query_count=search_query_count,
                tutorial_completion_count=tutorial_completion_count,
                plugin_publication_count=plugin_publication_count,
                community_activity_count=community_activity_count,
                ai_assistant_usage_count=ai_assistant_usage_count,
            )
        )

    async def list_range(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[PortalStatistic]:
        return await self._repo.list_range(organization_id, since=since, limit=limit)


__all__ = ["StatisticsService"]
