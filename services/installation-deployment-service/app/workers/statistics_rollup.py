"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**The window is always the last *completed* hour**, never the current
in-progress one, matching every prior rollup worker in this codebase.

**Organization discovery unions four independent activity sources**
(installation sessions, deployment jobs, deployment versions, TLS
certificates) rather than just one -- an organization whose only
activity in a given window was, say, registering a certificate would
otherwise never be rolled up at all, the same class of gap
``services/developer-portal-service``'s own search index rebuild
worker had to be fixed for (Prompt 074).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import CheckResultStatus, DeploymentJobStatus, DeploymentJobType
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000


class StatisticsRollupWorker:
    """Recomputes every organization's installation/deployment activity
    statistics."""

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

            all_organization_ids: set[UUID] = set()
            all_organization_ids.update(await repos.installation_sessions.list_organization_ids())
            all_organization_ids.update(await repos.jobs.list_organization_ids())
            all_organization_ids.update(await repos.versions.list_organization_ids())
            all_organization_ids.update(await repos.tls_certificates.list_organization_ids())

            for organization_id in all_organization_ids:
                sessions = await repos.installation_sessions.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                installation_count = sum(
                    1
                    for row in sessions
                    if row.started_at is not None and window_start <= row.started_at < window_end
                )

                jobs = await repos.jobs.list_recent(organization_id, limit=_MAX_ROWS_PER_ORG)
                deployment_count = sum(
                    1
                    for row in jobs
                    if DeploymentJobType(row.job_type) == DeploymentJobType.DEPLOY
                    and row.started_at is not None
                    and window_start <= row.started_at < window_end
                )
                success_count = sum(
                    1
                    for row in jobs
                    if DeploymentJobStatus(row.status) == DeploymentJobStatus.SUCCEEDED
                    and row.completed_at is not None
                    and window_start <= row.completed_at < window_end
                )
                failure_count = sum(
                    1
                    for row in jobs
                    if DeploymentJobStatus(row.status) == DeploymentJobStatus.FAILED
                    and row.completed_at is not None
                    and window_start <= row.completed_at < window_end
                )

                upgrades = await repos.upgrade_history.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                upgrade_count = sum(
                    1
                    for row in upgrades
                    if row.started_at is not None and window_start <= row.started_at < window_end
                )

                rollbacks = await repos.rollback_history.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                rollback_count = sum(
                    1
                    for row in rollbacks
                    if row.started_at is not None and window_start <= row.started_at < window_end
                )

                preflight_results = await repos.preflight_results.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                verification_results = await repos.verification_results.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                validation_failure_count = sum(
                    1
                    for row in preflight_results
                    if CheckResultStatus(row.status) == CheckResultStatus.FAILED
                    and window_start <= row.checked_at < window_end
                ) + sum(
                    1
                    for row in verification_results
                    if CheckResultStatus(row.status) == CheckResultStatus.FAILED
                    and window_start <= row.verified_at < window_end
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    installation_count=installation_count,
                    deployment_count=deployment_count,
                    upgrade_count=upgrade_count,
                    rollback_count=rollback_count,
                    validation_failure_count=validation_failure_count,
                    success_count=success_count,
                    failure_count=failure_count,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
