"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import SyncStatus, UpdateStatus
from app.models.operations import EdgeSynchronization, EdgeUpdate
from app.models.sites import EdgeSite
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")


class StatisticsRollupWorker:
    """Recomputes every organization's fleet statistics."""

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

            for organization_id in await repos.devices.list_organization_ids():
                sites_registered = (
                    await session.execute(
                        select(func.count())
                        .select_from(EdgeSite)
                        .where(
                            EdgeSite.organization_id == organization_id,
                            EdgeSite.created_at >= window_start,
                            EdgeSite.created_at < window_end,
                        )
                    )
                ).scalar_one()

                devices = await repos.devices.list_recent(organization_id, limit=5000)
                devices_online = sum(1 for d in devices if d.is_online)
                devices_offline = len(devices) - devices_online

                synchronizations_completed = (
                    await session.execute(
                        select(func.count())
                        .select_from(EdgeSynchronization)
                        .where(
                            EdgeSynchronization.organization_id == organization_id,
                            EdgeSynchronization.status == SyncStatus.COMPLETED,
                            EdgeSynchronization.completed_at >= window_start,
                            EdgeSynchronization.completed_at < window_end,
                        )
                    )
                ).scalar_one()

                synchronizations_failed = (
                    await session.execute(
                        select(func.count())
                        .select_from(EdgeSynchronization)
                        .where(
                            EdgeSynchronization.organization_id == organization_id,
                            EdgeSynchronization.status == SyncStatus.FAILED,
                            EdgeSynchronization.completed_at >= window_start,
                            EdgeSynchronization.completed_at < window_end,
                        )
                    )
                ).scalar_one()

                updates_completed = (
                    await session.execute(
                        select(func.count())
                        .select_from(EdgeUpdate)
                        .where(
                            EdgeUpdate.organization_id == organization_id,
                            EdgeUpdate.status == UpdateStatus.COMPLETED,
                            EdgeUpdate.completed_at >= window_start,
                            EdgeUpdate.completed_at < window_end,
                        )
                    )
                ).scalar_one()

                updates_failed = (
                    await session.execute(
                        select(func.count())
                        .select_from(EdgeUpdate)
                        .where(
                            EdgeUpdate.organization_id == organization_id,
                            EdgeUpdate.status == UpdateStatus.FAILED,
                            EdgeUpdate.completed_at >= window_start,
                            EdgeUpdate.completed_at < window_end,
                        )
                    )
                ).scalar_one()

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    sites_registered=sites_registered,
                    devices_online=devices_online,
                    devices_offline=devices_offline,
                    synchronizations_completed=synchronizations_completed,
                    synchronizations_failed=synchronizations_failed,
                    updates_completed=updates_completed,
                    updates_failed=updates_failed,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
