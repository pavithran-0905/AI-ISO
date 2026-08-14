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

from app.models.enums import (
    ClusterComplianceStatus,
    ClusterHealthStatus,
    PolicyPropagationStatus,
    UpgradeStatus,
)
from app.models.fleet import Cluster
from app.models.operations import ClusterCompliance, ClusterPolicy, ClusterUpgrade
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

            for organization_id in await repos.clusters.list_organization_ids():
                clusters_registered = (
                    await session.execute(
                        select(func.count())
                        .select_from(Cluster)
                        .where(
                            Cluster.organization_id == organization_id,
                            Cluster.registered_at >= window_start,
                            Cluster.registered_at < window_end,
                        )
                    )
                ).scalar_one()

                health_counts: dict[ClusterHealthStatus, int] = {}
                for cluster in await repos.clusters.list_recent(organization_id, limit=5000):
                    health_counts[cluster.health_status] = (
                        health_counts.get(cluster.health_status, 0) + 1
                    )

                policy_violations = (
                    await session.execute(
                        select(func.count())
                        .select_from(ClusterPolicy)
                        .where(
                            ClusterPolicy.organization_id == organization_id,
                            ClusterPolicy.propagation_status.in_(
                                [PolicyPropagationStatus.DRIFTED, PolicyPropagationStatus.FAILED]
                            ),
                        )
                    )
                ).scalar_one()

                compliance_violations = (
                    await session.execute(
                        select(func.count())
                        .select_from(ClusterCompliance)
                        .where(
                            ClusterCompliance.organization_id == organization_id,
                            ClusterCompliance.status == ClusterComplianceStatus.NON_COMPLIANT,
                        )
                    )
                ).scalar_one()

                upgrades_completed = (
                    await session.execute(
                        select(func.count())
                        .select_from(ClusterUpgrade)
                        .where(
                            ClusterUpgrade.organization_id == organization_id,
                            ClusterUpgrade.status == UpgradeStatus.COMPLETED,
                            ClusterUpgrade.completed_at >= window_start,
                            ClusterUpgrade.completed_at < window_end,
                        )
                    )
                ).scalar_one()

                upgrades_failed = (
                    await session.execute(
                        select(func.count())
                        .select_from(ClusterUpgrade)
                        .where(
                            ClusterUpgrade.organization_id == organization_id,
                            ClusterUpgrade.status == UpgradeStatus.FAILED,
                            ClusterUpgrade.completed_at >= window_start,
                            ClusterUpgrade.completed_at < window_end,
                        )
                    )
                ).scalar_one()

                total_node_count = sum(
                    (c.node_count or 0)
                    for c in await repos.clusters.list_recent(organization_id, limit=5000)
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    clusters_registered=clusters_registered,
                    clusters_healthy=health_counts.get(ClusterHealthStatus.HEALTHY, 0),
                    clusters_degraded=health_counts.get(ClusterHealthStatus.DEGRADED, 0),
                    clusters_unhealthy=health_counts.get(ClusterHealthStatus.UNHEALTHY, 0),
                    policy_violations=policy_violations,
                    compliance_violations=compliance_violations,
                    upgrades_completed=upgrades_completed,
                    upgrades_failed=upgrades_failed,
                    total_node_count=total_node_count,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
