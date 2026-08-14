"""The compliance sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Flags every cluster compliance assessment whose remediation deadline has
passed without a fresh (compliant) reassessment superseding it. Running
the actual compliance scan against a framework (CIS/NSA/PCI-DSS/...) is
target-specific work this build does not wire a scanner for -- this
worker reconciles what has already been recorded, which keeps overdue
remediations visible even between scans.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import ClusterComplianceStatus
from app.services.bundle import build_repositories
from app.services.notifications import FleetNotifier

logger = get_logger("app.workers.compliance_sweep")


class ComplianceSweepWorker:
    """Notifies for every compliance assessment overdue remediation."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: FleetNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every overdue remediation, returning how many were
        flagged."""
        now = datetime.now(UTC)
        flagged = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.compliance.list_organization_ids():
                for cluster in await repos.clusters.list_recent(organization_id, limit=5000):
                    for assessment in await repos.compliance.list_for_cluster(cluster.id):
                        if (
                            assessment.status
                            in (
                                ClusterComplianceStatus.NON_COMPLIANT,
                                ClusterComplianceStatus.PARTIALLY_COMPLIANT,
                            )
                            and assessment.remediation_due_at is not None
                            and assessment.remediation_due_at <= now
                        ):
                            await self._notifier.notify_compliance_failure(
                                cluster_id=str(cluster.id),
                                framework=str(assessment.framework),
                                status=str(assessment.status),
                            )
                            flagged += 1

        logger.info("compliance sweep completed", extra={"extra_fields": {"flagged": flagged}})
        return flagged


__all__ = ["ComplianceSweepWorker"]
