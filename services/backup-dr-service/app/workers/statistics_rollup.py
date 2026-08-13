"""The statistics rollup worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Idempotent per window.** A tick that fails partway through is safe to
repeat: the next tick recomputes and overwrites the same window's row
rather than adding a second copy that double-counts everything in it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.database.base import BaseModel
from shared_core.logging.logger import get_logger
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from app.models.backup import BackupJob
from app.models.enums import BackupJobStatus, ComplianceStatus, RestoreJobStatus
from app.models.recovery import DrTest, RestoreJob
from app.services.bundle import build_repositories
from app.services.statistics import StatisticsService

logger = get_logger("app.workers.statistics_rollup")


async def _count(
    session: AsyncSession,
    model: type[BaseModel],
    organization_id: UUID,
    column: InstrumentedAttribute[datetime | None],
    *,
    start: datetime,
    end: datetime,
    extra: tuple[ColumnElement[bool], ...] = (),
) -> int:
    stmt = (
        select(func.count())
        .select_from(model)
        .where(model.organization_id == organization_id, column >= start, column < end, *extra)
    )
    return (await session.execute(stmt)).scalar_one()


class StatisticsRollupWorker:
    """Recomputes every organization's backup/DR statistics."""

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

            for organization_id in await repos.targets.list_organization_ids():
                jobs_completed = await _count(
                    session,
                    BackupJob,
                    organization_id,
                    BackupJob.completed_at,
                    start=window_start,
                    end=window_end,
                    extra=(BackupJob.status == BackupJobStatus.COMPLETED,),
                )
                jobs_failed = await _count(
                    session,
                    BackupJob,
                    organization_id,
                    BackupJob.completed_at,
                    start=window_start,
                    end=window_end,
                    extra=(BackupJob.status == BackupJobStatus.FAILED,),
                )
                bytes_stmt = select(func.coalesce(func.sum(BackupJob.size_bytes), 0)).where(
                    BackupJob.organization_id == organization_id,
                    BackupJob.completed_at >= window_start,
                    BackupJob.completed_at < window_end,
                )
                bytes_backed_up = (await session.execute(bytes_stmt)).scalar_one()

                restore_completed = await _count(
                    session,
                    RestoreJob,
                    organization_id,
                    RestoreJob.completed_at,
                    start=window_start,
                    end=window_end,
                    extra=(
                        RestoreJob.status.in_(
                            [RestoreJobStatus.COMPLETED, RestoreJobStatus.VALIDATED]
                        ),
                    ),
                )
                restore_failed = await _count(
                    session,
                    RestoreJob,
                    organization_id,
                    RestoreJob.completed_at,
                    start=window_start,
                    end=window_end,
                    extra=(RestoreJob.status == RestoreJobStatus.FAILED,),
                )

                dr_tests = (
                    (
                        await session.execute(
                            select(DrTest).where(
                                DrTest.organization_id == organization_id,
                                DrTest.completed_at.is_not(None),
                                DrTest.completed_at >= window_start,
                                DrTest.completed_at < window_end,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                rpo_compliant = sum(1 for t in dr_tests if t.rpo_status is ComplianceStatus.MET)
                rpo_violated = sum(1 for t in dr_tests if t.rpo_status is ComplianceStatus.VIOLATED)
                rto_compliant = sum(1 for t in dr_tests if t.rto_status is ComplianceStatus.MET)
                rto_violated = sum(1 for t in dr_tests if t.rto_status is ComplianceStatus.VIOLATED)

                await service.roll_up_window(
                    organization_id,
                    window_start=window_start,
                    window_end=window_end,
                    jobs_completed=jobs_completed,
                    jobs_failed=jobs_failed,
                    bytes_backed_up=int(bytes_backed_up or 0),
                    restore_jobs_completed=restore_completed,
                    restore_jobs_failed=restore_failed,
                    mean_restore_duration_ms=None,
                    replication_jobs_lagging=0,
                    mean_replication_lag_seconds=None,
                    rpo_compliant_count=rpo_compliant,
                    rpo_violated_count=rpo_violated,
                    rto_compliant_count=rto_compliant,
                    rto_violated_count=rto_violated,
                )
                rolled += 1
            await session.commit()

        logger.info(
            "statistics rollup completed", extra={"extra_fields": {"organizations": rolled}}
        )
        return rolled


__all__ = ["StatisticsRollupWorker"]
