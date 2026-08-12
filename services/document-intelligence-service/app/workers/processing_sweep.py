"""The processing sweep worker (docs/063 "PROCESSING PIPELINE").

Claims queued jobs and runs the pipeline over them. **Leader-elected**
through ``shared_core.scheduler``; see :mod:`app.workers.registrar`.

**One session per job.** A failure on one document must not poison the
transaction the next one needs -- and a document silently missing from a
sweep is worse than one that visibly failed, because nothing will ever
look at it again.

**Claiming is what makes concurrency safe.** The repository claims rows
with ``FOR UPDATE SKIP LOCKED``, so two replicas take disjoint work rather
than both processing the same scan. That claim is only held for the life
of its session, which is why the session wraps exactly one job.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import JobStatus
from app.models.operations import DocumentProcessingJob
from app.services.bundle import build_repositories
from app.services.pipeline import PipelineConfig, PipelineService
from app.services.storage import DocumentStorage
from app.types import EventPublisher

logger = get_logger("app.workers.processing_sweep")


class ProcessingSweepWorker:
    """Runs queued pipeline jobs."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        config: PipelineConfig | None = None,
        ocr_engine: object | None = None,
        storage: DocumentStorage | None = None,
        batch_size: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._config = config or PipelineConfig()
        self._ocr = ocr_engine
        self._storage = storage
        self._batch_size = batch_size

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Process one batch of due jobs, returning how many ran."""
        job_ids = await self._claim()
        if not job_ids:
            return 0

        processed = 0
        for job_id in job_ids:
            if await self._run_one(job_id):
                processed += 1
        logger.info(
            "processing sweep completed",
            extra={"extra_fields": {"claimed": len(job_ids), "processed": processed}},
        )
        return processed

    async def _claim(self) -> list[object]:
        """Claim due jobs and mark them RUNNING, returning their ids.

        Claimed and released in one short transaction, then each job is
        re-loaded in its own session. Holding the ``SKIP LOCKED`` rows for
        the whole batch would block a second replica for as long as the
        slowest document takes -- which for a two-hundred-page scan is
        minutes of an idle replica.
        """
        async with self._session_factory() as session:
            repos = build_repositories(session)
            claimed = await repos.jobs.claim_due(datetime.now(UTC), limit=self._batch_size)
            ids = [job.id for job in claimed]
            for job in claimed:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(UTC)
            await session.commit()
            return ids

    async def _run_one(self, job_id: object) -> bool:
        """Run one job in its own session, returning whether it ran.

        A failure is recorded on the job and swallowed here: raising would
        abandon the sweep with the remaining jobs still marked RUNNING and
        nothing to move them on.
        """
        async with self._session_factory() as session:
            repos = build_repositories(session)
            job = await repos.jobs.get_by_id(job_id)  # type: ignore[arg-type]
            if job is None:  # pragma: no cover -- claimed a moment ago
                return False
            try:
                data = await self._load_bytes(job, repos)
                pipeline = PipelineService(
                    repositories=repos,
                    publish=self._publish_event,
                    config=self._config,
                    ocr_engine=self._ocr,
                )
                await pipeline.run(job, data)
                await session.commit()
                return True
            except Exception as error:
                await session.rollback()
                await self._record_failure(job_id, str(error))
                logger.warning(
                    "processing job failed",
                    extra={"extra_fields": {"job_id": str(job_id), "error": str(error)}},
                )
                return False

    async def _load_bytes(self, job: DocumentProcessingJob, repos: object) -> bytes:
        """The document's original bytes, from the object store.

        The original bytes, never the extracted text: text is what parsing
        produced, so a document's first run would have nothing to read.

        Raises:
            ValueError: When the job names no document, or no object store
                is configured. Both are recorded as job failures rather
                than silently producing an empty document.
        """
        if job.document_id is None:
            raise ValueError(f"Job {job.id!s} names no document.")
        if self._storage is None:
            raise ValueError(
                "No document object store is configured, so this worker cannot "
                "read the original bytes of any document."
            )
        document = await repos.documents.require_by_id(job.document_id)  # type: ignore[attr-defined]
        return await self._storage.get(bucket=document.storage_bucket, key=document.storage_key)

    async def _record_failure(self, job_id: object, error: str) -> None:
        """Mark a job failed in a fresh session.

        A fresh one because the session that raised has been rolled back,
        and writing the failure through it would be lost with everything
        else in that transaction -- leaving the job RUNNING forever.
        """
        async with self._session_factory() as session:
            repos = build_repositories(session)
            job = await repos.jobs.get_by_id(job_id)  # type: ignore[arg-type]
            if job is None:  # pragma: no cover
                return
            job.status = JobStatus.FAILED
            job.error = error[:2_000]
            job.completed_at = datetime.now(UTC)
            job.attempts = max(job.attempts, 1)
            await session.commit()


__all__ = ["ProcessingSweepWorker"]
