"""The quota reset sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Resets every quota whose own ``period_end`` has arrived back to zero
consumption for a freshly computed next period, and notifies Quota
Warning for a quota that has crossed its own warning threshold but has
not yet reset.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.quotas.engine import is_quota_warning
from app.services.bundle import build_repositories
from app.services.notifications import DeveloperNotifier
from app.services.quotas import QuotaService

logger = get_logger("app.workers.quota_reset_sweep")


class QuotaResetSweepWorker:
    """Resets expired quota periods and warns of imminent quota
    exhaustion."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: DeveloperNotifier,
        warning_threshold_percent: float,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_threshold_percent = warning_threshold_percent

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's quotas, returning how many were
        checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            quota_service = QuotaService(repos.api_quotas)

            for organization_id in await repos.api_quotas.list_organization_ids():
                for quota in await repos.api_quotas.list_all(organization_id):
                    if now >= quota.period_end:
                        await quota_service.reset_for_new_period(quota, now=now)
                    elif is_quota_warning(
                        used_value=quota.used_value,
                        limit_value=quota.limit_value,
                        threshold_percent=self._warning_threshold_percent,
                    ):
                        used_percent = (quota.used_value / quota.limit_value) * 100
                        await self._notifier.notify_quota_warning(
                            quota_type=str(quota.quota_type), used_percent=used_percent
                        )
                    checked += 1
            await session.commit()

        logger.info("quota reset sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["QuotaResetSweepWorker"]
