"""The budget sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Recomputes every budget's current spend from its account's recorded
costs within the budget period, publishing ``BudgetThresholdExceeded``
on crossing into warning/critical/exceeded.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.finops import CloudBudgetService
from app.types import EventPublisher

logger = get_logger("app.workers.budget_sweep")


class BudgetSweepWorker:
    """Recomputes spend and threshold status for every budget."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        critical_threshold: float,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._critical_threshold = critical_threshold

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Recompute every budget's spend, returning how many were
        checked."""
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = CloudBudgetService(repos.budgets, publish=self._publish_event)

            for organization_id in await repos.budgets.list_organization_ids():
                for budget in await repos.budgets.list_recent(organization_id, limit=5000):
                    if budget.account_id is None:
                        continue
                    current_spend = await repos.costs.total_for_account(
                        budget.account_id, since=budget.period_start
                    )
                    await service.refresh_spend(
                        budget,
                        current_spend=current_spend,
                        critical_threshold=self._critical_threshold,
                    )
                    checked += 1
            await session.commit()

        logger.info("budget sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["BudgetSweepWorker"]
