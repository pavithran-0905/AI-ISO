"""The compliance sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies for every compliance assessment past its remediation
deadline -- mirroring
``services/multi-cluster-management-service/app/workers/compliance_sweep.py``'s
own precedent exactly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import CloudComplianceStatus
from app.services.bundle import build_repositories
from app.services.notifications import CloudNotifier

logger = get_logger("app.workers.compliance_sweep")

_VIOLATION_STATUSES = frozenset(
    {CloudComplianceStatus.NON_COMPLIANT, CloudComplianceStatus.PARTIALLY_COMPLIANT}
)


class ComplianceSweepWorker:
    """Notifies for every overdue compliance remediation."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: CloudNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every overdue compliance remediation, returning
        how many were flagged."""
        now = datetime.now(UTC)
        flagged = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.compliance.list_organization_ids():
                for assessment in await repos.compliance.list_recent(organization_id, limit=5000):
                    if assessment.status not in _VIOLATION_STATUSES:
                        continue
                    if assessment.remediation_due_at is None or assessment.remediation_due_at > now:
                        continue
                    await self._notifier.notify_compliance_violation(
                        account_id=str(assessment.account_id),
                        framework=str(assessment.framework),
                        status=str(assessment.status),
                    )
                    flagged += 1

        logger.info("compliance sweep completed", extra={"extra_fields": {"flagged": flagged}})
        return flagged


__all__ = ["ComplianceSweepWorker"]
