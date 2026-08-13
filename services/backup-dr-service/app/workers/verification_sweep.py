"""The verification sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Selects which completed jobs are due for their next verification check
via ``app.verification.engine.select_sample`` and queues a ``PENDING``
:class:`~app.models.backup.BackupVerification` row for each.

**Queuing is this worker's whole job; performing the read is not.**
Actually re-reading archive bytes from storage to recompute a checksum
is an I/O-bound operation against MinIO or a target's own storage layer,
which this build does not wire a client for -- the seam is declared
here rather than faked with a comparison that would trivially always
pass (comparing a job's own recorded checksum against itself).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.backup import BackupVerification
from app.models.enums import BackupJobStatus, VerificationKind, VerificationStatus
from app.services.bundle import build_repositories
from app.verification.engine import VerifiableArchive, select_sample

logger = get_logger("app.workers.verification_sweep")


class VerificationSweepWorker:
    """Queues verification checks for jobs due their next check."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        max_age_days: int,
        sample_fraction: float,
    ) -> None:
        self._session_factory = session_factory
        self._max_age_days = max_age_days
        self._sample_fraction = sample_fraction

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Queue verification checks, returning how many were queued."""
        now = datetime.now(UTC)
        max_age = now - timedelta(days=self._max_age_days)
        queued = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.targets.list_organization_ids():
                jobs = await repos.jobs.list_recent(
                    organization_id, status=BackupJobStatus.COMPLETED, limit=500
                )
                candidates: list[VerifiableArchive] = []
                for job in jobs:
                    if job.checksum is None:
                        continue
                    latest = await repos.verifications.latest_for_job(job.id)
                    candidates.append(
                        VerifiableArchive(
                            archive_id=str(job.id),
                            last_verified_at=latest.verified_at if latest else None,
                        )
                    )
                due = select_sample(candidates, fraction=self._sample_fraction, max_age=max_age)
                for archive in due:
                    await repos.verifications.create(
                        BackupVerification(
                            organization_id=organization_id,
                            job_id=UUID(archive.archive_id),
                            verification_kind=VerificationKind.PERIODIC,
                            status=VerificationStatus.PENDING,
                        )
                    )
                    queued += 1
            await session.commit()

        logger.info("verification sweep completed", extra={"extra_fields": {"queued": queued}})
        return queued


__all__ = ["VerificationSweepWorker"]
