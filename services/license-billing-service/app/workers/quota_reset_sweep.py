"""The quota reset sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Proactively opens the current calendar window's ``QuotaUsage`` row for
every quota, at zero usage, ahead of any request that would otherwise
create it lazily on first use -- so a customer's first request of a new
period is never the one paying for window creation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.usage import QuotaUsage
from app.quotas.engine import compute_period_window
from app.services.bundle import build_repositories

logger = get_logger("app.workers.quota_reset_sweep")


class QuotaResetSweepWorker:
    """Opens the current period's usage window for every quota that
    does not already have one."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's quotas, returning how many
        windows were newly opened."""
        now = datetime.now(UTC)
        opened = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.quotas.list_organization_ids():
                for quota in await repos.quotas.list_recent(organization_id, limit=5000):
                    period_start, period_end = compute_period_window(quota.period, now=now)
                    existing = await repos.quota_usage.find_window(
                        quota.id, period_start=period_start
                    )
                    if existing is not None:
                        continue
                    await repos.quota_usage.create(
                        QuotaUsage(
                            organization_id=quota.organization_id,
                            quota_id=quota.id,
                            period_start=period_start,
                            period_end=period_end,
                            used_value=0.0,
                        )
                    )
                    opened += 1
            await session.commit()

        logger.info("quota reset sweep completed", extra={"extra_fields": {"opened": opened}})
        return opened


__all__ = ["QuotaResetSweepWorker"]
