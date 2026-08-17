"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**The window is always the last *completed* hour**, never the current
in-progress one (``window_end = now().replace(minute=0, second=0,
microsecond=0)``, ``window_start = window_end - 1h``) -- the same
established AI-IOS convention every prior rollup worker in this
codebase uses.

**``sdk_download_count`` is always ``0``.** This service integrates
SDK generation (Prompt 071) but does not itself own any download
tracking table -- ``services/sdk-cli-service`` owns
``sdk_downloads``. Reported as a real zero, not omitted, so the column
is never silently misleading about what it does and does not measure
in this build.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000
_ERROR_STATUS_THRESHOLD = 400


class StatisticsRollupWorker:
    """Recomputes every organization's developer platform activity
    statistics."""

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
            all_organization_ids.update(await repos.api_usage.list_organization_ids())
            all_organization_ids.update(await repos.developer_accounts.list_organization_ids())
            all_organization_ids.update(await repos.api_keys.list_organization_ids())
            all_organization_ids.update(await repos.applications.list_organization_ids())

            for organization_id in all_organization_ids:
                usage_events = await repos.api_usage.list_since(
                    organization_id, since=window_start, limit=_MAX_ROWS_PER_ORG
                )
                windowed_events = [
                    event
                    for event in usage_events
                    if window_start <= event.occurred_at < window_end
                ]
                api_call_count = len(windowed_events)
                error_count = sum(
                    1 for event in windowed_events if event.status_code >= _ERROR_STATUS_THRESHOLD
                )
                average_latency_ms = (
                    sum(event.latency_ms for event in windowed_events) / api_call_count
                    if api_call_count
                    else 0.0
                )

                developers = await repos.developer_accounts.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                registration_count = sum(
                    1 for row in developers if window_start <= row.created_at < window_end
                )

                applications = await repos.applications.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                application_count = sum(
                    1 for row in applications if window_start <= row.created_at < window_end
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    api_call_count=api_call_count,
                    registration_count=registration_count,
                    application_count=application_count,
                    sdk_download_count=0,
                    error_count=error_count,
                    average_latency_ms=average_latency_ms,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
