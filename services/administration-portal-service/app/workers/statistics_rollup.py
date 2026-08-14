"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**``user_count`` is a scoped proxy: the distinct administrators with a
currently-enabled session, not an end-user count.** This service holds
no end-user table of its own -- that is the identity/auth service's
system of record (Prompt 030/032 integration) -- so the honest reading
available here is administrative session activity, not tenant end
users.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.engine import compute_availability_fraction
from app.models.enums import HealthCheckStatus
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")


class StatisticsRollupWorker:
    """Recomputes every organization's platform statistics."""

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

            for organization_id in await repos.tenants.list_organization_ids():
                tenants = await repos.tenants.list_recent(organization_id, limit=5_000)
                sessions = await repos.admin_sessions.list_enabled(organization_id)
                jobs = await repos.jobs.list_recent(organization_id, limit=5_000)
                background_job_count = sum(
                    1 for job in jobs if window_start <= job.queued_at < window_end
                )
                api_request_count = await repos.api_usage.total_requests_for_org(
                    organization_id, since=window_start
                )
                security_event_count = await repos.security_events.count_since(
                    organization_id, since=window_start
                )
                checks = await repos.health_checks.list_all(organization_id)
                healthy_count = sum(
                    1 for check in checks if check.status == HealthCheckStatus.HEALTHY
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    tenant_count=len(tenants),
                    user_count=len({s.admin_user_id for s in sessions}),
                    api_request_count=api_request_count,
                    background_job_count=background_job_count,
                    security_event_count=security_event_count,
                    platform_availability_fraction=compute_availability_fraction(
                        healthy_count, len(checks)
                    ),
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
