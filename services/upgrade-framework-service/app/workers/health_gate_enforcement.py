"""The health-gate enforcement worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Implements the "Automatic Pause" capability docs/076's own
HEALTH-GATED UPGRADES section names: any upgrade job still ``RUNNING``
that has accumulated a ``FAILED`` verification result is stopped
autonomously (moved to ``FAILED``) rather than being left to run to
completion against a health signal that has already turned red. This
worker only detects and pauses -- an actual rollback remains an
explicit, caller-initiated ``POST /rollback`` action, the same
separation of concerns
``services/installation-deployment-service``'s own rollback framework
established (Prompt 075).
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import UpgradeJobStatus
from app.services.bundle import build_repositories
from app.services.notifications import UpgradeNotifier
from app.services.upgrade import UpgradeJobService

logger = get_logger("app.workers.health_gate_enforcement")


class HealthGateEnforcementWorker:
    """Auto-pauses running upgrade jobs with a failed health-gate
    check."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: UpgradeNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Auto-pause every organization's running upgrade jobs that
        have a failed verification result, returning how many were
        paused."""
        now = datetime.now(UTC)
        paused = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            job_service = UpgradeJobService(repos.jobs, repos.history)

            for organization_id in await repos.jobs.list_organization_ids():
                for job in await repos.jobs.list_running(organization_id):
                    failed_checks = await repos.verification_results.list_failed_for_job(job.id)
                    if not failed_checks:
                        continue
                    await job_service.complete(
                        job,
                        status=UpgradeJobStatus.FAILED,
                        now=now,
                        error_message="Health gate failed: automatic pause triggered.",
                    )
                    await self._notifier.notify_upgrade_failed(
                        reason="Health gate failed: automatic pause triggered."
                    )
                    paused += 1
            await session.commit()

        logger.info("health gate enforcement completed", extra={"extra_fields": {"paused": paused}})
        return paused


__all__ = ["HealthGateEnforcementWorker"]
