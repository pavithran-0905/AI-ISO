"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.

**The window is always the last *completed* hour**, never the current
in-progress one, matching every prior rollup worker in this codebase.

**Organization discovery unions three independent activity sources**
(test runs, test results, quality gates) rather than just one -- an
organization whose only activity in a given window was defining a
quality gate would otherwise never be rolled up at all, the same class
of gap prior rollup workers in this codebase had to be fixed for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics.engine import quality_score as compute_quality_score
from app.models.enums import QualityGateStatus, TestResultStatus
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")

_MAX_ROWS_PER_ORG = 5_000


class StatisticsRollupWorker:
    """Recomputes every organization's QA activity statistics."""

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
            all_organization_ids.update(await repos.test_runs.list_organization_ids())
            all_organization_ids.update(await repos.test_results.list_organization_ids())
            all_organization_ids.update(await repos.coverage_reports.list_organization_ids())

            for organization_id in all_organization_ids:
                runs = await repos.test_runs.list_recent(organization_id, limit=_MAX_ROWS_PER_ORG)
                test_run_count = sum(
                    1
                    for row in runs
                    if row.started_at is not None and window_start <= row.started_at < window_end
                )

                results = await repos.test_results.list_recent(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                )
                windowed_results = [
                    row for row in results if window_start <= row.created_at < window_end
                ]
                pass_count = sum(
                    1
                    for row in windowed_results
                    if TestResultStatus(row.status) == TestResultStatus.PASSED
                )
                fail_count = sum(
                    1
                    for row in windowed_results
                    if TestResultStatus(row.status) == TestResultStatus.FAILED
                )
                flaky_count = sum(
                    1
                    for row in windowed_results
                    if TestResultStatus(row.status) == TestResultStatus.FLAKY
                )

                gates = await repos.quality_gates.list_all(organization_id, limit=_MAX_ROWS_PER_ORG)
                quality_gate_failure_count = sum(
                    1
                    for row in gates
                    if QualityGateStatus(row.status) == QualityGateStatus.FAILED
                    and window_start <= row.updated_at < window_end
                )

                total_results = len(windowed_results)
                pass_ratio = pass_count / total_results if total_results else 0.0
                coverage_reports = await repos.coverage_reports.list_all(organization_id, limit=1)
                coverage_percentage = coverage_reports[0].percentage if coverage_reports else 0.0
                total_gates = len(gates)
                gate_pass_ratio = (
                    sum(
                        1
                        for row in gates
                        if QualityGateStatus(row.status) == QualityGateStatus.PASSED
                    )
                    / total_gates
                    if total_gates
                    else 0.0
                )
                score = compute_quality_score(
                    pass_rate_value=pass_ratio,
                    coverage_percentage=coverage_percentage,
                    quality_gate_pass_rate=gate_pass_ratio,
                )

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    test_run_count=test_run_count,
                    pass_count=pass_count,
                    fail_count=fail_count,
                    flaky_count=flaky_count,
                    quality_gate_failure_count=quality_gate_failure_count,
                    quality_score=score,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
