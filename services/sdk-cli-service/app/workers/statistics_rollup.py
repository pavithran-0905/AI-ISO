"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**``auth_failure_count`` is always ``0``.** A failed CLI authentication
attempt is notified directly (see
`app.services.cli_sessions.CliSessionService.authenticate`) but never
persisted as a row anywhere in this service's own database -- there is
nothing this rollup could truthfully count it from. Reported as a real
zero, not omitted, so the column is never silently misleading about
what it does and does not measure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import CliUpdateStatus, PluginStatus
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000


class StatisticsRollupWorker:
    """Recomputes every organization's SDK/CLI activity statistics."""

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
            all_organization_ids.update(await repos.cli_sessions.list_organization_ids())
            all_organization_ids.update(await repos.cli_plugins.list_organization_ids())
            all_organization_ids.update(await repos.cli_versions.list_organization_ids())
            all_organization_ids.update(await repos.cli_updates.list_organization_ids())
            all_organization_ids.update(await repos.cli_usage.list_organization_ids())
            all_organization_ids.update(await repos.sdk_releases.list_organization_ids())
            all_organization_ids.update(await repos.sdk_downloads.list_organization_ids())

            for organization_id in all_organization_ids:
                downloads = await repos.sdk_downloads.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                sdk_download_count = sum(
                    1 for row in downloads if window_start <= row.downloaded_at < window_end
                )

                updates = await repos.cli_updates.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                cli_download_count = sum(
                    1
                    for row in updates
                    if row.status == CliUpdateStatus.APPLIED
                    and row.applied_at is not None
                    and window_start <= row.applied_at < window_end
                )

                usage = await repos.cli_usage.list_recent(organization_id, limit=_MAX_ROWS_PER_ORG)
                command_execution_count = sum(
                    1 for row in usage if window_start <= row.executed_at < window_end
                )

                plugins = await repos.cli_plugins.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                plugin_install_count = sum(
                    1
                    for row in plugins
                    if row.status == PluginStatus.INSTALLED
                    and window_start <= row.updated_at < window_end
                )

                sessions = await repos.cli_sessions.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                auth_success_count = sum(
                    1 for row in sessions if window_start <= row.started_at < window_end
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    sdk_download_count=sdk_download_count,
                    cli_download_count=cli_download_count,
                    command_execution_count=command_execution_count,
                    plugin_install_count=plugin_install_count,
                    auth_success_count=auth_success_count,
                    auth_failure_count=0,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
