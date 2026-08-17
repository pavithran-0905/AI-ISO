"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**The window is always the last *completed* hour**, never the current
in-progress one, matching every prior rollup worker in this codebase.

**Four of the eight counters are always ``0``, honestly.** This
service has no persisted table for documentation page views, search
queries, tutorial completions, or AI assistant usage -- the domain
events for the latter two exist (``TutorialCompleted``,
``AIAssistantUsed``) but nothing writes a row when they fire (see
``app.tutorials.engine``'s own docstring for why completion tracking
specifically has nowhere to live), and there was never a page-view or
search-query log table in docs/074's own DATABASE TABLES section to
begin with. Reported as real zeros, not omitted, so these columns are
never silently misleading about what they do and do not measure in
this build.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import PluginSubmissionStatus
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000


class StatisticsRollupWorker:
    """Recomputes every organization's portal activity statistics."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, window_hours: int = 1
    ) -> None:
        self._session_factory = session_factory
        self._window_hours = window_hours

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

            all_organization_ids: set[UUID] = set()
            all_organization_ids.update(await repos.sessions.list_organization_ids())
            all_organization_ids.update(await repos.plugin_submissions.list_organization_ids())
            all_organization_ids.update(await repos.sdk_downloads.list_organization_ids())
            all_organization_ids.update(await repos.community_posts.list_organization_ids())

            for organization_id in all_organization_ids:
                sessions = await repos.sessions.list_active(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                portal_visit_count = sum(
                    1 for row in sessions if window_start <= row.issued_at < window_end
                )

                downloads = await repos.sdk_downloads.list_since(
                    organization_id, since=window_start, limit=_MAX_ROWS_PER_ORG
                )
                sdk_download_count = sum(
                    1 for row in downloads if window_start <= row.downloaded_at < window_end
                )

                submissions = await repos.plugin_submissions.list_recent(
                    organization_id, status=PluginSubmissionStatus.APPROVED, limit=_MAX_ROWS_PER_ORG
                )
                plugin_publication_count = sum(
                    1 for row in submissions if window_start <= row.updated_at < window_end
                )

                posts = await repos.community_posts.list_visible(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                post_count = sum(1 for row in posts if window_start <= row.created_at < window_end)

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    portal_visit_count=portal_visit_count,
                    documentation_view_count=0,
                    sdk_download_count=sdk_download_count,
                    search_query_count=0,
                    tutorial_completion_count=0,
                    plugin_publication_count=plugin_publication_count,
                    community_activity_count=post_count,
                    ai_assistant_usage_count=0,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
