"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**The window is always the last *completed* hour**, never the current
in-progress one, matching every prior rollup worker in this codebase.

**Organization discovery unions four independent activity sources**
(release versions, release builds, release promotions, downloads)
rather than just one -- an organization whose only activity in a given
window was a download would otherwise never be rolled up at all, the
same class of gap prior rollup workers in this codebase had to be
fixed for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.engine import build_success_rate, promotion_success_rate, release_health_score
from app.models.enums import BuildStatus, PromotionStatus
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000


class StatisticsRollupWorker:
    """Recomputes every organization's release activity statistics."""

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
            all_organization_ids.update(await repos.release_versions.list_organization_ids())
            all_organization_ids.update(await repos.release_builds.list_organization_ids())
            all_organization_ids.update(await repos.release_promotions.list_organization_ids())
            all_organization_ids.update(await repos.download_statistics.list_organization_ids())

            for organization_id in all_organization_ids:
                versions = await repos.release_versions.list_all(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                release_count = sum(
                    1 for row in versions if window_start <= row.created_at < window_end
                )

                builds = await repos.release_builds.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                windowed_builds = [
                    row for row in builds if window_start <= row.created_at < window_end
                ]
                succeeded_builds = sum(
                    1 for row in windowed_builds if BuildStatus(row.status) == BuildStatus.SUCCEEDED
                )
                b_rate = build_success_rate(succeeded_builds, len(windowed_builds))

                promotions = await repos.release_promotions.list_all(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                windowed_promotions = [
                    row for row in promotions if window_start <= row.created_at < window_end
                ]
                completed_promotions = sum(
                    1
                    for row in windowed_promotions
                    if PromotionStatus(row.status) == PromotionStatus.COMPLETED
                )
                p_rate = promotion_success_rate(completed_promotions, len(windowed_promotions))

                downloads = await repos.download_statistics.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                download_count = sum(
                    1 for row in downloads if window_start <= row.downloaded_at < window_end
                )

                score = release_health_score(
                    build_success_rate_value=b_rate, promotion_success_rate_value=p_rate
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    release_count=release_count,
                    promotion_count=len(windowed_promotions),
                    download_count=download_count,
                    avg_release_success_rate=score,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
