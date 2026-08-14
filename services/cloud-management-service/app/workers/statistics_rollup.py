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

from app.finops.engine import BudgetStatus, classify_budget_status
from app.models.enums import CloudComplianceStatus
from app.models.operations import CloudCompliance, CloudCost, CloudDrift
from app.models.resources import CloudResource
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_VIOLATION_STATUSES = frozenset(
    {CloudComplianceStatus.NON_COMPLIANT, CloudComplianceStatus.PARTIALLY_COMPLIANT}
)


class StatisticsRollupWorker:
    """Recomputes every organization's cloud fleet statistics."""

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

            for organization_id in await repos.resources.list_organization_ids():
                resources_discovered = (
                    await session.execute(
                        select(func.count())
                        .select_from(CloudResource)
                        .where(
                            CloudResource.organization_id == organization_id,
                            CloudResource.discovered_at >= window_start,
                            CloudResource.discovered_at < window_end,
                        )
                    )
                ).scalar_one()

                resources_provisioned = (
                    await session.execute(
                        select(func.count())
                        .select_from(CloudResource)
                        .where(
                            CloudResource.organization_id == organization_id,
                            CloudResource.provisioned_at >= window_start,
                            CloudResource.provisioned_at < window_end,
                        )
                    )
                ).scalar_one()

                total_cost = (
                    await session.execute(
                        select(func.coalesce(func.sum(CloudCost.amount), 0.0)).where(
                            CloudCost.organization_id == organization_id,
                            CloudCost.period_start >= window_start,
                            CloudCost.period_start < window_end,
                        )
                    )
                ).scalar_one()

                budgets_exceeded = 0
                for budget in await repos.budgets.list_recent(organization_id, limit=5000):
                    status = classify_budget_status(
                        budget.current_spend,
                        budget.amount,
                        warning_threshold=budget.threshold_fraction,
                        critical_threshold=max(budget.threshold_fraction, 0.95),
                    )
                    if status == BudgetStatus.EXCEEDED:
                        budgets_exceeded += 1

                drift_detected_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(CloudDrift)
                        .where(
                            CloudDrift.organization_id == organization_id,
                            CloudDrift.detected_at >= window_start,
                            CloudDrift.detected_at < window_end,
                        )
                    )
                ).scalar_one()

                compliance_violations = (
                    await session.execute(
                        select(func.count())
                        .select_from(CloudCompliance)
                        .where(
                            CloudCompliance.organization_id == organization_id,
                            CloudCompliance.status.in_(_VIOLATION_STATUSES),
                            CloudCompliance.assessed_at >= window_start,
                            CloudCompliance.assessed_at < window_end,
                        )
                    )
                ).scalar_one()

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    resources_discovered=resources_discovered,
                    resources_provisioned=resources_provisioned,
                    total_cost=float(total_cost),
                    budgets_exceeded=budgets_exceeded,
                    drift_detected_count=drift_detected_count,
                    compliance_violations=compliance_violations,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
