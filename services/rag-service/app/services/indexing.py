"""Indexing (docs/062 "INDEXING PIPELINE").

Turning stored chunks into searchable vectors: embed, upsert, mark. The
expensive, rate-limited, retryable half of the pipeline, kept apart from
:mod:`app.services.ingestion` so a parse failure never consumes an
embedding quota and an embedding outage never loses a parse.

**Nothing is embedded twice.** Each vector records the hash of the exact
text it was produced from, so a chunk whose text is unchanged is skipped
even when the document around it was re-ingested, re-versioned, or
re-queued. Embedding is the only part of this service that costs money
per call, and re-embedding an unchanged corpus is the single largest way
to waste that money.

**A job that half-worked reports as ``PARTIAL``, never as success.** Nine
hundred documents indexed and a hundred failed is not a completed
reindex, and recording it as one hides the hundred forever -- nobody
re-runs a job that says it worked.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.embeddings.encoder import content_hash
from app.embeddings.service import EmbeddingService
from app.events.rag_events import (
    DocumentIndexedEvent,
    EmbeddingGeneratedEvent,
    ReindexCompletedEvent,
)
from app.models.analytics import IndexingJob, RagAudit
from app.models.document import Document, DocumentChunk
from app.models.enums import (
    AuditAction,
    DocumentStatus,
    IndexKind,
    IndexStatus,
)
from app.repositories.analytics import IndexingJobRepository, RagAuditRepository
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import EmbeddingVectorRepository
from app.types import EventPublisher
from app.vector_store.base import VectorRecord, VectorStore, VectorStoreError

logger = get_logger("app.services.indexing")

_SOURCE_SERVICE = "rag-service"

DEFAULT_STALE_AFTER_SECONDS = 1_800.0
"""Thirty minutes. A job still ``RUNNING`` after this long is assumed to
belong to a worker that died: long enough that a genuinely slow batch is
not stolen mid-flight, short enough that a crash does not strand its
documents unindexed for a whole day."""


@dataclass(slots=True)
class IndexResult:
    """What indexing one document produced."""

    document_id: UUID
    embedded: int = 0
    skipped: int = 0
    """Chunks that already had their own vector for this model."""
    reused: int = 0
    """Chunks whose text was already embedded under a *different* chunk
    id -- copied rather than paid for again. An embedding is a pure
    function of (text, model), so a copy is the same answer, not an
    approximation."""
    tokens: int = 0
    cost_usd: float = 0.0
    cache_hits: int = 0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    @property
    def total(self) -> int:
        return self.embedded + self.skipped + self.reused

    @property
    def paid_for(self) -> int:
        """Chunks that actually cost an embedding call."""
        return self.embedded


@dataclass(slots=True)
class JobResult:
    """What running one indexing job produced."""

    job: IndexingJob
    results: list[IndexResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for row in self.results if row.succeeded)

    @property
    def failed(self) -> int:
        return sum(1 for row in self.results if not row.succeeded)

    @property
    def status(self) -> IndexStatus:
        """``COMPLETED`` only when nothing failed.

        A job with any failure is ``PARTIAL`` even if most documents
        worked, because the number anyone needs to act on is the failure
        count and a green status buries it.
        """
        if not self.results:
            return IndexStatus.COMPLETED
        if self.failed == len(self.results):
            return IndexStatus.FAILED
        return IndexStatus.PARTIAL if self.failed else IndexStatus.COMPLETED


class IndexingService:
    """Embeds chunks and keeps the vector store in step with them."""

    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        chunks: DocumentChunkRepository,
        vectors: EmbeddingVectorRepository,
        jobs: IndexingJobRepository,
        audit: RagAuditRepository,
        *,
        embeddings: EmbeddingService,
        store: VectorStore,
        publish_event: EventPublisher,
        batch_size: int = 64,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._chunks = chunks
        self._vectors = vectors
        self._jobs = jobs
        self._audit = audit
        self._embeddings = embeddings
        self._store = store
        self._publish_event = publish_event
        self._batch_size = max(1, batch_size)
        self._stale_after = stale_after_seconds

    # -- indexing one document ------------------------------------------

    async def index_document(
        self, organization_id: UUID, document_id: UUID, *, force: bool = False
    ) -> IndexResult:
        """Embed and store every chunk of one document's live version.

        Args:
            force: Re-embed even chunks whose text is unchanged. For
                recovering from a vector store that lost data -- the hash
                check would otherwise skip exactly the chunks that need
                rewriting, since the *chunks* are fine and only the
                vectors are missing.

        Raises:
            NotFoundError: If the document does not exist in this
                organization.
        """
        document = await self._documents.require_in_org(organization_id, document_id)
        chunks = await self._current_chunks(document)
        if not chunks:
            # Nothing to embed and nothing wrong: a document whose parse
            # produced no chunks was already refused at ingestion, so
            # reaching here means it is genuinely up to date.
            return IndexResult(document_id=document.id)

        try:
            result = await self._embed_chunks(document, chunks, force=force)
        except (VectorStoreError, ValidationError) as exc:
            await self._mark_failed(document, str(exc))
            logger.warning(
                "Indexing failed.",
                extra={"extra_fields": {"document_id": str(document.id), "error": str(exc)}},
            )
            return IndexResult(document_id=document.id, error=str(exc))

        await self._mark_indexed(document, result)
        await self._audit_indexed(document, result)
        await self._publish_event(
            DocumentIndexedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=document.organization_id,
                payload={
                    "document_id": str(document.id),
                    "vectors": result.embedded,
                    "skipped": result.skipped,
                    "reused": result.reused,
                    "model": self._embeddings.model,
                },
            )
        )
        return result

    async def _current_chunks(self, document: Document) -> list[DocumentChunk]:
        """Every chunk of the document's live version.

        The live version only, never every version. A document
        re-ingested five times has five versions' worth of chunks in the
        table, and embedding them all would cost five times as much and
        put four superseded copies of the same text into the index --
        where they would compete with the current one for the same
        queries and win about as often.
        """
        version = await self._versions.get_current(document.id)
        if version is None:
            return []
        return await self._chunks.list_for_version(version.id)

    async def _embed_chunks(
        self, document: Document, chunks: Sequence[DocumentChunk], *, force: bool
    ) -> IndexResult:
        """Embed *chunks* in batches and write both vector homes.

        Two writes per chunk, deliberately: the ``embedding_vectors`` row
        (the durable record, with its cost and token accounting) and the
        vector store (what search reads). For the pgvector backend these
        are the same table and the second write is a no-op replace; for
        any other backend they are different systems, and the accounting
        has to survive swapping the store.
        """
        result = IndexResult(document_id=document.id)
        pending: list[tuple[DocumentChunk, str]] = []
        reused: list[VectorRecord] = []

        for chunk in chunks:
            digest = content_hash(chunk.content, model=self._embeddings.model)
            if force:
                pending.append((chunk, digest))
                continue

            existing = await self._vectors.get_for_chunk(
                chunk.id, model_name=self._embeddings.model
            )
            if existing is not None and existing.content_hash == digest:
                result.skipped += 1
                await self._mark_chunk_embedded(chunk)
                continue

            # This chunk has no vector, but its *text* may already have
            # one. Re-parsing a document builds new chunk rows with new
            # ids, so a lookup keyed on the chunk finds nothing even when
            # every paragraph is byte-identical. Without this, changing
            # one line of a long document pays to re-embed all of it.
            twin = await self._vectors.find_by_content_hash(
                document.organization_id, digest, model_name=self._embeddings.model
            )
            if twin is not None and len(twin.vector) == self._embeddings.dimensions:
                reused.append(
                    self._to_record(document, chunk, list(twin.vector), digest, cost_usd=0.0)
                )
                result.reused += 1
                continue
            pending.append((chunk, digest))

        if reused:
            await self._store.upsert(reused)
            for record in reused:
                await self._mark_chunk_embedded(_by_id(chunks, record.chunk_id))

        for start in range(0, len(pending), self._batch_size):
            window = pending[start : start + self._batch_size]
            batch = await self._embeddings.embed([chunk.content for chunk, _ in window])
            if len(batch.vectors) != len(window):
                raise ValidationError(
                    f"The embedding provider returned {len(batch.vectors)} vectors for "
                    f"{len(window)} chunks. Storing them would pair chunks with other "
                    "chunks' vectors, so the batch is refused."
                )
            result.tokens += batch.tokens
            result.cost_usd += batch.cost_usd
            result.cache_hits += batch.cache_hits

            billable = sum(chunk.token_count for chunk, _ in window) or len(window)
            records = [
                self._to_record(
                    document,
                    chunk,
                    vector,
                    digest,
                    cost_usd=batch.cost_usd * (chunk.token_count or 1) / billable,
                )
                for (chunk, digest), vector in zip(window, batch.vectors, strict=True)
            ]
            await self._store.upsert(records)
            for chunk, _ in window:
                await self._mark_chunk_embedded(chunk)
            result.embedded += len(records)

        if result.embedded:
            await self._publish_event(
                EmbeddingGeneratedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=document.organization_id,
                    payload={
                        "document_id": str(document.id),
                        "vectors": result.embedded,
                        "tokens": result.tokens,
                        "cost_usd": round(result.cost_usd, 6),
                        "cache_hits": result.cache_hits,
                        "model": self._embeddings.model,
                    },
                )
            )
        return result

    def _to_record(
        self,
        document: Document,
        chunk: DocumentChunk,
        vector: list[float],
        digest: str,
        *,
        cost_usd: float,
    ) -> VectorRecord:
        """Pair one vector with the scope every search has to filter on.

        The document's classification and roles are copied onto the
        record rather than joined at query time. A store that is not
        PostgreSQL cannot join against ``documents`` at all, so a scope
        that lived only there would be unenforceable the moment the
        backend changed -- and the failure mode of an unenforceable scope
        is disclosure.
        """
        return VectorRecord(
            chunk_id=chunk.id,
            document_id=document.id,
            organization_id=document.organization_id,
            vector=vector,
            content=chunk.content,
            project_scope_id=document.project_scope_id,
            classification=str(document.classification),
            allowed_roles=tuple(document.allowed_roles),
            metadata={"title": document.title},
            content_hash=digest,
            token_count=chunk.token_count,
            cost_usd=round(cost_usd, 8),
        )

    async def _mark_chunk_embedded(self, chunk: DocumentChunk) -> None:
        """Flip the denormalised flag the indexing sweep selects on."""
        if chunk.is_embedded and chunk.embedding_model == self._embeddings.model:
            return
        chunk.is_embedded = True
        chunk.embedding_model = self._embeddings.model
        await self._chunks.update(chunk)

    async def _mark_indexed(self, document: Document, result: IndexResult) -> None:
        """Record that this document's current content is now searchable.

        ``indexed_checksum`` is set to the document's current checksum,
        which is what makes the incremental sweep able to tell "changed
        since indexing" from "never indexed" -- see
        :meth:`~app.repositories.document.DocumentRepository.list_needing_index`.
        """
        document.status = DocumentStatus.INDEXED
        document.last_indexed_at = datetime.now(UTC)
        document.indexed_checksum = document.checksum
        document.error = None
        await self._documents.update(document)

    async def _mark_failed(self, document: Document, reason: str) -> None:
        """Record an indexing failure on the document itself."""
        document.status = DocumentStatus.FAILED
        document.error = reason[:1_000]
        await self._documents.update(document)

    # -- jobs -------------------------------------------------------------

    async def queue_job(
        self,
        organization_id: UUID,
        *,
        kind: IndexKind = IndexKind.INCREMENTAL,
        document_id: UUID | None = None,
        knowledge_source_id: UUID | None = None,
        priority: int = 100,
        scheduled_at: datetime | None = None,
        requested_by: str | None = None,
        max_attempts: int = 3,
    ) -> IndexingJob:
        """Queue an indexing job.

        Raises:
            ValidationError: If *max_attempts* is below one. A job that
                may never be attempted is a row that sits in ``QUEUED``
                forever and looks like a stuck worker.
        """
        if max_attempts < 1:
            raise ValidationError(
                f"max_attempts must be at least 1, got {max_attempts!r}; a job that is "
                "never attempted stays QUEUED forever and reads as a stuck worker."
            )
        return await self._jobs.create(
            IndexingJob(
                organization_id=organization_id,
                document_id=document_id,
                knowledge_source_id=knowledge_source_id,
                kind=kind,
                status=IndexStatus.QUEUED,
                priority=priority,
                scheduled_at=scheduled_at or datetime.now(UTC),
                max_attempts=max_attempts,
                requested_by=requested_by,
            )
        )

    async def run_job(self, job: IndexingJob) -> JobResult:
        """Run one queued job to completion.

        Raises:
            ValidationError: If the job is not ``QUEUED``. Running a job
                that is already ``RUNNING`` is how the same documents get
                embedded twice and billed twice.
        """
        if job.status != IndexStatus.QUEUED:
            raise ValidationError(
                f"IndexingJob {job.id!s} is {job.status!s}, not queued. Re-running a "
                "job already in flight would embed and bill its documents twice."
            )
        started = datetime.now(UTC)
        job.status = IndexStatus.RUNNING
        job.started_at = started
        job.attempts += 1
        await self._jobs.update(job)

        targets = await self._targets(job)
        job.documents_total = len(targets)

        outcome = JobResult(job=job)
        for document in targets:
            outcome.results.append(
                await self.index_document(
                    job.organization_id, document.id, force=job.kind == IndexKind.FULL
                )
            )

        job.documents_succeeded = outcome.succeeded
        job.documents_failed = outcome.failed
        job.vectors_created = sum(row.embedded for row in outcome.results)
        job.tokens_embedded = sum(row.tokens for row in outcome.results)
        job.cost_usd = round(sum(row.cost_usd for row in outcome.results), 6)
        job.status = outcome.status
        job.completed_at = datetime.now(UTC)
        job.duration_ms = (job.completed_at - started).total_seconds() * 1_000.0
        job.error = self._first_error(outcome)
        await self._jobs.update(job)

        await self._publish_event(
            ReindexCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=job.organization_id,
                payload={
                    "job_id": str(job.id),
                    "status": str(job.status),
                    "documents_total": job.documents_total,
                    "documents_succeeded": job.documents_succeeded,
                    "documents_failed": job.documents_failed,
                    "vectors_created": job.vectors_created,
                    "cost_usd": job.cost_usd,
                },
            )
        )
        await self._audit.create(
            RagAudit(
                organization_id=job.organization_id,
                action=AuditAction.REINDEXED,
                entity_type="indexing_job",
                entity_id=job.id,
                actor_id=job.requested_by,
                occurred_at=datetime.now(UTC),
                summary=(
                    f"Indexing job finished {job.status!s}: {job.documents_succeeded} "
                    f"indexed, {job.documents_failed} failed."
                ),
                succeeded=job.status != IndexStatus.FAILED,
            )
        )
        return outcome

    @staticmethod
    def _first_error(outcome: JobResult) -> str | None:
        """The first failure's message, for the job row.

        One message rather than all of them: the row has to stay readable,
        and every failure is already recorded on its own document. This is
        the pointer, not the record.
        """
        for row in outcome.results:
            if row.error:
                return row.error[:1_000]
        return None

    async def _targets(self, job: IndexingJob) -> list[Document]:
        """The documents one job covers.

        Raises:
            NotFoundError: If the job names a document that does not
                exist. Failing loudly beats indexing nothing and
                reporting success, which is what an empty target list
                would produce.
        """
        if job.document_id is not None:
            document = await self._documents.get_by_id(job.document_id)
            if document is None or document.organization_id != job.organization_id:
                raise NotFoundError(
                    f"IndexingJob {job.id!s} names document {job.document_id!s}, which "
                    f"was not found in organization {job.organization_id!s}."
                )
            return [document]

        if job.kind == IndexKind.FULL:
            candidates = await self._documents.list_for_org(job.organization_id, limit=10_000)
        else:
            candidates = await self._documents.list_needing_index(job.organization_id, limit=10_000)
        if job.knowledge_source_id is not None:
            candidates = [
                row for row in candidates if row.knowledge_source_id == job.knowledge_source_id
            ]
        return [row for row in candidates if row.status not in _UNINDEXABLE]

    async def run_due_jobs(
        self, moment: datetime | None = None, *, limit: int = 5
    ) -> list[JobResult]:
        """Run every queued job whose time has come, priority first."""
        now = moment or datetime.now(UTC)
        return [await self.run_job(job) for job in await self._jobs.list_due(now, limit=limit)]

    async def reclaim_stale_jobs(self, moment: datetime | None = None) -> list[IndexingJob]:
        """Re-queue or fail jobs abandoned by a dead worker.

        Re-queued while attempts remain, failed once they are exhausted.
        Neither branch is optional: leaving them ``RUNNING`` means the
        documents stay unindexed behind a row that claims otherwise, and
        re-queueing forever turns one poisonous document into an infinite
        billing loop.
        """
        now = moment or datetime.now(UTC)
        cutoff = now - timedelta(seconds=self._stale_after)
        reclaimed: list[IndexingJob] = []
        for job in await self._jobs.list_stale_running(cutoff):
            if job.attempts < job.max_attempts:
                job.status = IndexStatus.QUEUED
                job.started_at = None
                job.error = (
                    f"Re-queued after no progress for {self._stale_after:.0f}s; the "
                    "worker holding it is assumed to have died."
                )
            else:
                job.status = IndexStatus.FAILED
                job.completed_at = now
                job.error = (
                    f"Abandoned after {job.attempts} attempt(s); each one stopped "
                    "making progress before finishing."
                )
            reclaimed.append(await self._jobs.update(job))
            logger.warning(
                "Reclaimed a stale indexing job.",
                extra={"extra_fields": {"job_id": str(job.id), "status": str(job.status)}},
            )
        return reclaimed

    async def _audit_indexed(self, document: Document, result: IndexResult) -> None:
        """Append the audit row for one indexed document."""
        await self._audit.create(
            RagAudit(
                organization_id=document.organization_id,
                action=AuditAction.INDEXED,
                entity_type="document",
                entity_id=document.id,
                entity_reference=document.title,
                occurred_at=datetime.now(UTC),
                summary=(
                    f"Indexed {result.embedded} chunk(s), reused {result.reused}, "
                    f"skipped {result.skipped} already embedded, using "
                    f"{self._embeddings.model}."
                ),
                succeeded=True,
            )
        )


def _by_id(chunks: Sequence[DocumentChunk], chunk_id: UUID) -> DocumentChunk:
    """The chunk with *chunk_id*, which is always present by construction."""
    return next(chunk for chunk in chunks if chunk.id == chunk_id)


_UNINDEXABLE = frozenset({DocumentStatus.ARCHIVED, DocumentStatus.DELETED, DocumentStatus.PENDING})
"""Statuses a sweep must skip. ``ARCHIVED`` and ``DELETED`` were taken
out of retrieval on purpose and re-indexing would put them back;
``PENDING`` has no chunks yet, so indexing it embeds nothing and marks it
``INDEXED``, which is worse than leaving it alone."""


__all__ = [
    "DEFAULT_STALE_AFTER_SECONDS",
    "IndexResult",
    "IndexingService",
    "JobResult",
]
