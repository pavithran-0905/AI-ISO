"""The account health sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Downgrades a still-valid account to ``DEGRADED`` once its last real
revalidation has gone stale -- an account this service has not actually
rechecked recently is not still confidently ``HEALTHY``, without
claiming it is actually invalid (that would require a real recheck,
which only :meth:`~app.services.accounts.CloudAccountService.revalidate`
performs).
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.engine import classify_account_health, is_account_stale
from app.services.bundle import build_repositories

logger = get_logger("app.workers.account_health_sweep")


class AccountHealthSweepWorker:
    """Reclassifies every account's health from revalidation
    staleness."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, stale_threshold_minutes: int
    ) -> None:
        self._session_factory = session_factory
        self._stale_threshold_minutes = stale_threshold_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Reclassify every account's health, returning how many were
        checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.accounts.list_organization_ids():
                for account in await repos.accounts.list_recent(organization_id, limit=5000):
                    stale = is_account_stale(
                        account.last_validated_at,
                        now=now,
                        threshold_minutes=self._stale_threshold_minutes,
                    )
                    account.health_status = classify_account_health(
                        is_valid=account.is_valid, is_stale=stale
                    )
                    await repos.accounts.update(account)
                    checked += 1
            await session.commit()

        logger.info("account health sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["AccountHealthSweepWorker"]
