"""The indexing sweep worker (docs/062 "INDEXING PIPELINE").

Runs queued indexing jobs and reclaims the ones a dead worker abandoned.
**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Reclamation runs before dispatch, every tick.** A job stuck in
``RUNNING`` behind a worker that died holds documents unindexed behind a
row claiming otherwise, and dispatching first would keep starting new work
while the stranded work stayed stranded.

**One session per job.** A failure on one job must not poison the
transaction the next one needs, and a job silently skipped is worse than
one that visibly failed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.embeddings.service import EmbeddingService
from app.repositories.analytics import IndexingJobRepository, RagAuditRepository
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import EmbeddingVectorRepository
from app.services.indexing import IndexingService
from app.types import EventPublisher
from app.vector_store.registry import build_store

logger = get_logger("app.workers.indexing_sweep")


class IndexingSweepWorker:
    """Runs due indexing jobs and reclaims stale ones."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        embeddings: EmbeddingService,
        publish_event: EventPublisher,
        vector_store: str = "pgvector",
        batch_size: int = 25,
        max_jobs_per_tick: int = 5,
    ) -> None:
        self._session_factory = session_factory
        self._embeddings = embeddings
        self._publish_event = publish_event
        self._vector_store = vector_store
        self._batch_size = batch_size
        self._max_jobs = max_jobs_per_tick

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Reclaim, then run due jobs; returns how many jobs ran."""
        reclaimed = await self._reclaim()
        due = await self._due_job_ids()
        ran = 0
        for job_id in due:
            if await self._run_one(job_id):
                ran += 1
        logger.info(
            "Indexing sweep complete.",
            extra={"extra_fields": {"reclaimed": reclaimed, "due": len(due), "ran": ran}},
        )
        return ran

    async def _reclaim(self) -> int:
        """Re-queue or fail jobs abandoned mid-flight."""
        try:
            async with self._session_factory() as session:
                service = self._build(session)
                reclaimed = await service.reclaim_stale_jobs()
                await session.commit()
                return len(reclaimed)
        except Exception as exc:
            logger.warning(
                "Reclaiming stale indexing jobs failed; the sweep continues.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return 0

    async def _due_job_ids(self) -> list[UUID]:
        """Ids of queued jobs whose time has come, priority first.

        Ids rather than the rows themselves: each job is then run under
        its own session, and an ORM object attached to a session that has
        since closed cannot be updated.
        """
        async with self._session_factory() as session:
            jobs = await IndexingJobRepository(session).list_due(
                datetime.now(UTC), limit=self._max_jobs
            )
            return [job.id for job in jobs]

    async def _run_one(self, job_id: UUID) -> bool:
        """Run one job under its own session."""
        try:
            async with self._session_factory() as session:
                repository = IndexingJobRepository(session)
                job = await repository.get_by_id(job_id)
                if job is None:
                    return False
                await self._build(session).run_job(job)
                await session.commit()
            return True
        except Exception as exc:
            logger.warning(
                "An indexing job failed; the rest of the sweep continues.",
                extra={"extra_fields": {"job_id": str(job_id), "error": str(exc)}},
            )
            return False

    def _build(self, session: AsyncSession) -> IndexingService:
        """An indexing service bound to one session."""
        return IndexingService(
            DocumentRepository(session),
            DocumentVersionRepository(session),
            DocumentChunkRepository(session),
            EmbeddingVectorRepository(session),
            IndexingJobRepository(session),
            RagAuditRepository(session),
            embeddings=self._embeddings,
            store=build_store(
                self._vector_store,
                session=session,
                model_name=self._embeddings.model,
                dimensions=self._embeddings.dimensions,
                embedding_provider=str(self._embeddings.provider),
            ),
            publish_event=self._publish_event,
            batch_size=self._batch_size,
        )


__all__ = ["IndexingSweepWorker"]
