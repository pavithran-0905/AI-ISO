"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**The window is always the last *completed* hour**, never the current
in-progress one, matching every prior rollup worker in this codebase.

**Organization discovery unions three independent activity sources**
(hardening runs, security findings, vulnerability scans) rather than
just one -- an organization whose only activity in a given window was
a new security finding would otherwise never be rolled up at all, the
same class of gap prior rollup workers in this codebase had to be
fixed for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.engine import hardening_score
from app.models.enums import CheckResultStatus
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000


class StatisticsRollupWorker:
    """Recomputes every organization's hardening activity statistics."""

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
            all_organization_ids.update(await repos.hardening_runs.list_organization_ids())
            all_organization_ids.update(await repos.security_findings.list_organization_ids())
            all_organization_ids.update(await repos.vulnerability_scans.list_organization_ids())

            for organization_id in all_organization_ids:
                runs = await repos.hardening_runs.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                hardening_run_count = sum(
                    1
                    for row in runs
                    if row.started_at is not None and window_start <= row.started_at < window_end
                )

                results = await repos.hardening_results.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                windowed_results = [
                    row for row in results if window_start <= row.created_at < window_end
                ]
                passed_count = sum(
                    1
                    for row in windowed_results
                    if CheckResultStatus(row.status) == CheckResultStatus.PASSED
                )
                score = hardening_score(passed_count, len(windowed_results))

                findings = await repos.security_findings.list_all(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                security_finding_count = sum(
                    1 for row in findings if window_start <= row.created_at < window_end
                )

                vulnerabilities = await repos.vulnerability_scans.list_all(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                vulnerability_count = sum(
                    1 for row in vulnerabilities if window_start <= row.created_at < window_end
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    hardening_run_count=hardening_run_count,
                    security_finding_count=security_finding_count,
                    vulnerability_count=vulnerability_count,
                    avg_hardening_score=score,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
