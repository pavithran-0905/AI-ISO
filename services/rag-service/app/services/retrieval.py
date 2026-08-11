"""Retrieval (docs/062 "RETRIEVAL STRATEGIES", "HYBRID SEARCH",
"CONTEXT ASSEMBLY").

The read path: run the arms a strategy asks for, fuse them, rerank, and
assemble a context block with citations. Everything up to fusion is a
pure function already tested on its own -- see :mod:`app.hybrid_search`,
:mod:`app.reranking`, :mod:`app.context` -- so what lives here is the
composition, the access scope, and the recording.

**Every retrieval is recorded, including the ones that found nothing.**
A ``RetrievalQuery`` row per call, with its timing split three ways and
its access scope written down. The empty results are the valuable half:
they are the list of questions the corpus cannot answer, which is the
only output of this service that tells anybody what to write next.

**The access scope goes into the query, never around it.** Roles,
clearance, and project scope are pushed into the vector search's own
WHERE clause and applied to the keyword arm before ranking. Retrieving
first and filtering after would leak through the result count, the
ranking, and the latency, and would make ``top_k`` mean different things
to different callers.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.context.assembler import AssembledContext, ContextChunk, assemble
from app.embeddings.service import EmbeddingService
from app.events.rag_events import ContextGeneratedEvent, RetrievalExecutedEvent
from app.graph_rag.retriever import GraphRetriever
from app.hybrid_search import bm25
from app.hybrid_search.fusion import FusedItem, RankedItem, fuse, to_ranked
from app.models.analytics import RagAudit
from app.models.document import Document, DocumentChunk
from app.models.enums import (
    AuditAction,
    DocumentStatus,
    FeedbackVerdict,
    FusionMethod,
    RerankMethod,
    RetrievalOutcome,
    RetrievalStrategy,
)
from app.models.retrieval import (
    RerankingResult,
    RetrievalFeedback,
    RetrievalQuery,
    RetrievalResult,
)
from app.repositories.analytics import RagAuditRepository
from app.repositories.document import DocumentChunkRepository, DocumentRepository
from app.repositories.retrieval import (
    RerankingResultRepository,
    RetrievalFeedbackRepository,
    RetrievalQueryRepository,
    RetrievalResultRepository,
)
from app.reranking.engine import Candidate, rerank
from app.security.access import AccessContext, can_read
from app.types import EventPublisher
from app.vector_store.base import VectorQuery, VectorStore, VectorStoreError

logger = get_logger("app.services.retrieval")

_SOURCE_SERVICE = "rag-service"

VECTOR_ARM = "vector"
KEYWORD_ARM = "keyword"
GRAPH_ARM = "graph"

DEFAULT_MIN_SIMILARITY = 0.0
"""The default relevance floor: none.

**This is what makes ``EMPTY`` outcomes -- and therefore the unanswered-
question report -- depend on configuration rather than luck.** A vector
search with no floor always returns its top *k*, however unrelated they
are, so every query "succeeds" and nothing is ever recorded as
unanswered. A floor above zero is what turns "the nearest thing in the
corpus" into "an answer".

It defaults to zero anyway, because the right value depends entirely on
the embedding model in use and a number invented here would be wrong for
most of them -- silently discarding good results under one model and
admitting noise under another. Operators set it once, per deployment,
through the service's own configuration; callers can override per query.
"""

DEFAULT_CANDIDATE_MULTIPLIER = 4
"""How many candidates to gather per requested result. Reranking can only
reorder what it was given, so a top-10 request that fetched exactly ten
candidates has nothing to rerank -- the reranker would return the same
ten in a different order and the diversity pass would have no alternatives
to swap in."""

_RETRIEVABLE = frozenset(
    {
        DocumentStatus.CHUNKED,
        DocumentStatus.EMBEDDED,
        DocumentStatus.INDEXED,
        DocumentStatus.PUBLISHED,
    }
)
"""Statuses a document must be in to be returned. ``ARCHIVED`` and
``DELETED`` were withdrawn on purpose; ``FAILED`` and ``PENDING`` have
partial or absent chunks, and half a document is worse than none because
nothing marks it as half."""


@dataclass(slots=True)
class RetrievedChunk:
    """One result, with everything a caller needs to cite it."""

    chunk: DocumentChunk
    document: Document
    rank: int
    score: float
    arm_scores: dict[str, float] = field(default_factory=dict)
    arm_ranks: dict[str, int] = field(default_factory=dict)
    rank_before_rerank: int = 0
    score_before_rerank: float = 0.0

    @property
    def key(self) -> str:
        return str(self.chunk.id)


@dataclass(slots=True)
class RetrievalOutput:
    """What one retrieval produced."""

    query: RetrievalQuery
    results: list[RetrievedChunk] = field(default_factory=list)
    denied: int = 0
    candidates: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.results


@dataclass(slots=True)
class ContextOutput:
    """A retrieval plus the context block assembled from it."""

    retrieval: RetrievalOutput
    context: AssembledContext


class RetrievalService:
    """Searches the corpus and assembles context from what it finds."""

    def __init__(
        self,
        documents: DocumentRepository,
        chunks: DocumentChunkRepository,
        queries: RetrievalQueryRepository,
        results: RetrievalResultRepository,
        rerankings: RerankingResultRepository,
        feedback: RetrievalFeedbackRepository,
        audit: RagAuditRepository,
        *,
        embeddings: EmbeddingService,
        store: VectorStore,
        publish_event: EventPublisher,
        graph: GraphRetriever | None = None,
        candidate_multiplier: int = DEFAULT_CANDIDATE_MULTIPLIER,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._queries = queries
        self._results = results
        self._rerankings = rerankings
        self._feedback = feedback
        self._audit = audit
        self._embeddings = embeddings
        self._store = store
        self._publish_event = publish_event
        self._graph = graph
        self._multiplier = max(1, candidate_multiplier)
        self._min_similarity = min_similarity

    # -- retrieval ---------------------------------------------------------

    async def retrieve(
        self,
        context: AccessContext,
        query_text: str,
        *,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        fusion_method: FusionMethod = FusionMethod.RRF,
        rerank_method: RerankMethod | None = RerankMethod.HYBRID,
        top_k: int = 10,
        min_similarity: float | None = None,
        metadata_filters: Mapping[str, str] | None = None,
        document_ids: Sequence[UUID] = (),
        weights: Mapping[str, float] | None = None,
    ) -> RetrievalOutput:
        """Search the corpus and return the best chunks the caller may see.

        Raises:
            ValidationError: If the query is blank or *top_k* is below one.
        """
        cleaned = query_text.strip()
        if not cleaned:
            raise ValidationError("Cannot retrieve with an empty query.")
        if top_k < 1:
            raise ValidationError(f"top_k must be at least 1, got {top_k!r}.")

        started = time.perf_counter()
        record = await self._open_query(
            context,
            cleaned,
            strategy=strategy,
            fusion_method=fusion_method,
            top_k=top_k,
            metadata_filters=dict(metadata_filters or {}),
        )

        try:
            arms, timings = await self._run_arms(
                context,
                cleaned,
                strategy=strategy,
                top_k=top_k,
                min_similarity=(self._min_similarity if min_similarity is None else min_similarity),
                metadata_filters=metadata_filters or {},
                document_ids=document_ids,
            )
        except VectorStoreError as exc:
            await self._close_query(
                record, outcome=RetrievalOutcome.FAILED, started=started, error=str(exc)
            )
            raise

        fused = (
            fuse(
                arms,
                method=fusion_method,
                weights=dict(weights) if weights else _default_weights(arms),
            )
            if arms
            else []
        )
        record.candidate_count = len(fused)

        allowed, denied = await self._resolve(context, fused)
        reranked, rerank_ms = self._rerank(allowed, method=rerank_method, top_k=top_k)

        output = RetrievalOutput(
            query=record, results=reranked, denied=denied, candidates=len(fused)
        )
        await self._persist_results(record, output, rerank_method=rerank_method)
        await self._close_query(
            record,
            outcome=self._outcome(output),
            started=started,
            timings={**timings, "rerank_ms": rerank_ms},
            output=output,
        )
        await self._publish_event(
            RetrievalExecutedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=context.organization_id,
                payload={
                    "query_id": str(record.id),
                    "strategy": str(strategy),
                    "results": len(output.results),
                    "denied": denied,
                    "candidates": len(fused),
                    "outcome": str(record.outcome),
                },
            )
        )
        return output

    async def _run_arms(
        self,
        context: AccessContext,
        query_text: str,
        *,
        strategy: RetrievalStrategy,
        top_k: int,
        min_similarity: float,
        metadata_filters: Mapping[str, str],
        document_ids: Sequence[UUID],
    ) -> tuple[dict[str, list[RankedItem]], dict[str, float]]:
        """Run whichever arms *strategy* calls for, and time them.

        An arm that finds nothing contributes an empty list rather than
        being omitted -- fusion needs to know it ran and found nothing,
        which is different from not having run.
        """
        wanted = _ARMS_FOR_STRATEGY[RetrievalStrategy(strategy)]
        depth = top_k * self._multiplier
        arms: dict[str, list[RankedItem]] = {}
        timings: dict[str, float] = {}

        if VECTOR_ARM in wanted:
            embed_started = time.perf_counter()
            vector = await self._embeddings.embed_one(query_text)
            timings["embedding_ms"] = (time.perf_counter() - embed_started) * 1_000.0
            search_started = time.perf_counter()
            arms[VECTOR_ARM] = await self._vector_arm(
                context,
                vector,
                depth=depth,
                min_similarity=min_similarity,
                metadata_filters=metadata_filters,
                document_ids=document_ids,
            )
            timings["search_ms"] = (time.perf_counter() - search_started) * 1_000.0

        if KEYWORD_ARM in wanted:
            keyword_started = time.perf_counter()
            arms[KEYWORD_ARM] = await self._keyword_arm(context, query_text, depth=depth)
            timings["search_ms"] = timings.get("search_ms", 0.0) + (
                (time.perf_counter() - keyword_started) * 1_000.0
            )

        if GRAPH_ARM in wanted and self._graph is not None and self._graph.enabled:
            arms[GRAPH_ARM] = await self._graph_arm(context, query_text, depth=depth)

        return arms, timings

    async def _vector_arm(
        self,
        context: AccessContext,
        vector: list[float],
        *,
        depth: int,
        min_similarity: float,
        metadata_filters: Mapping[str, str],
        document_ids: Sequence[UUID],
    ) -> list[RankedItem]:
        """Semantic search, scoped inside the store's own query."""
        matches = await self._store.search(
            VectorQuery(
                organization_id=context.organization_id,
                vector=vector,
                top_k=depth,
                project_scope_id=None,
                caller_roles=tuple(sorted(context.roles)),
                max_classification=str(context.clearance),
                metadata_filters=dict(metadata_filters),
                document_ids=tuple(document_ids),
                min_similarity=min_similarity,
            )
        )
        return to_ranked([(str(match.chunk_id), match.score) for match in matches])

    async def _keyword_arm(
        self, context: AccessContext, query_text: str, *, depth: int
    ) -> list[RankedItem]:
        """Lexical search: PostgreSQL selects candidates, BM25 ranks them.

        BM25 needs term statistics over a corpus, and the corpus it is
        given here is the candidate set rather than the whole tenant.
        That makes the IDF local, which is the accepted cost of not
        loading every chunk into the process on every query -- the
        ordering within a candidate set is what the arm contributes, and
        fusion only ever consumes its ranks.
        """
        rows = await self._chunks.search_keyword(
            context.organization_id, query_text, limit=depth * 2
        )
        if not rows:
            return []
        index = bm25.build_index([(str(row.id), row.content) for row in rows])
        return to_ranked([(item.doc_id, item.score) for item in index.top(query_text, limit=depth)])

    async def _graph_arm(
        self, context: AccessContext, query_text: str, *, depth: int
    ) -> list[RankedItem]:
        """The GraphRAG arm: entities the query names, and their neighbours.

        Graph nodes are not chunks, so this arm contributes only where a
        node carries the chunk it came from. A node with no chunk is real
        knowledge that this arm cannot cite, and returning it as a result
        would produce a citation pointing at nothing.
        """
        if self._graph is None:
            return []
        subgraph = await self._graph.retrieve(query_text, context.organization_id)
        if subgraph.is_empty:
            return []
        scored: list[tuple[str, float]] = []
        for position, node in enumerate(subgraph.nodes[:depth]):
            chunk_id = str(node.properties.get("chunk_id", "")) if node.properties else ""
            if chunk_id:
                scored.append((chunk_id, 1.0 / (position + 1)))
        return to_ranked(scored)

    async def _resolve(
        self, context: AccessContext, fused: Sequence[FusedItem]
    ) -> tuple[list[RetrievedChunk], int]:
        """Load the chunks behind fused keys, dropping what the caller may
        not see.

        A second access check even though the vector arm already filtered:
        the keyword and graph arms do not go through the vector store, so
        without this a lexical match would return a document the semantic
        arm would have refused. Two arms disagreeing about who may read
        what is not a policy, it is a hole.
        """
        if not fused:
            return [], 0
        chunk_ids = [UUID(item.key) for item in fused]
        rows = await self._chunks.list_by_ids(context.organization_id, chunk_ids)
        by_id = {str(row.id): row for row in rows}

        document_ids = {row.document_id for row in rows}
        documents = {
            document.id: document
            for document in await self._documents.list_by_ids(
                context.organization_id, list(document_ids)
            )
        }

        allowed: list[RetrievedChunk] = []
        denied = 0
        for position, item in enumerate(fused, start=1):
            chunk = by_id.get(item.key)
            if chunk is None:
                # The chunk was deleted between indexing and this query.
                # Not a denial -- nothing was withheld, it is simply gone.
                continue
            document = documents.get(chunk.document_id)
            if document is None or document.status not in _RETRIEVABLE:
                continue
            if not can_read(context, document):
                denied += 1
                continue
            allowed.append(
                RetrievedChunk(
                    chunk=chunk,
                    document=document,
                    rank=position,
                    score=item.score,
                    arm_scores=dict(item.contributions),
                    arm_ranks=dict(item.source_ranks),
                    rank_before_rerank=position,
                    score_before_rerank=item.score,
                )
            )
        return allowed, denied

    def _rerank(
        self,
        candidates: Sequence[RetrievedChunk],
        *,
        method: RerankMethod | None,
        top_k: int,
    ) -> tuple[list[RetrievedChunk], float]:
        """Reorder and truncate to *top_k*.

        ``None`` skips reranking entirely and keeps fusion order, which is
        what a caller wanting a cheap, purely lexical lookup asks for.
        """
        if not candidates:
            return [], 0.0
        if method is None:
            trimmed = list(candidates[:top_k])
            for position, item in enumerate(trimmed, start=1):
                item.rank = position
            return trimmed, 0.0

        started = time.perf_counter()
        by_key = {item.key: item for item in candidates}
        ordered = rerank(
            [
                self._to_candidate(item, _fusion_confidence(position, len(candidates)))
                for position, item in enumerate(candidates)
            ],
            method=method,
            limit=top_k,
        )
        elapsed = (time.perf_counter() - started) * 1_000.0

        final: list[RetrievedChunk] = []
        for position, scored in enumerate(ordered, start=1):
            item = by_key[scored.key]
            item.rank = position
            item.score = scored.score
            final.append(item)
        return final, elapsed

    @staticmethod
    def _to_candidate(item: RetrievedChunk, confidence: float) -> Candidate:
        """Bridge a retrieved chunk into the pure reranking engine.

        *confidence* is supplied explicitly rather than left to the
        reranker's fallback, and that is load-bearing. The fallback clamps
        the first-stage score into ``[0, 1]``, and a Reciprocal Rank Fusion
        score is about ``1/(60 + rank)`` -- roughly 0.016 for every
        candidate. Clamped, those are indistinguishable, so the relevance
        signal that carries 55% of the hybrid reranker's weight becomes a
        constant and the final order is decided entirely by freshness,
        metadata, and classification. Observed live: the only chunk that
        actually matched a query, found by both arms at the top of each,
        ranked sixth because it was classified ``secret``.

        It also makes the reranker behave the same under every fusion
        method. Weighted-score fusion produces values near 1.0 and RRF
        near 0.016; feeding the raw score through would make the same
        reranker aggressive under one and inert under the other.
        """
        return Candidate(
            key=item.key,
            score=item.score,
            confidence=confidence,
            rank=item.rank_before_rerank,
            content=item.chunk.content,
            document_id=str(item.document.id),
            chunk_kind=item.chunk.chunk_kind,
            updated_at=item.document.updated_at,
            classification=str(item.document.classification),
            metadata={"title": item.document.title, **_string_metadata(item.chunk)},
        )

    # -- context -----------------------------------------------------------

    async def build_context(
        self,
        context: AccessContext,
        query_text: str,
        *,
        max_tokens: int = 4_000,
        include_citations: bool = True,
        allow_partial: bool = False,
        **retrieval_kwargs: object,
    ) -> ContextOutput:
        """Retrieve, then assemble a context block with citations.

        Raises:
            ValidationError: If *max_tokens* is not positive.
        """
        if max_tokens < 1:
            raise ValidationError(f"max_tokens must be at least 1, got {max_tokens!r}.")

        retrieved = await self.retrieve(context, query_text, **retrieval_kwargs)  # type: ignore[arg-type]
        assembled = assemble(
            [_to_context_chunk(item) for item in retrieved.results],
            max_tokens=max_tokens,
            include_citations=include_citations,
            allow_partial=allow_partial,
        )
        await self._mark_included(retrieved, assembled)
        await self._publish_event(
            ContextGeneratedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=context.organization_id,
                payload={
                    "query_id": str(retrieved.query.id),
                    "chunks_included": len(assembled.included),
                    "chunks_excluded": len(assembled.excluded),
                    "tokens": assembled.token_count,
                    "budget": assembled.budget,
                    "truncated": assembled.truncated,
                },
            )
        )
        await self._audit.create(
            RagAudit(
                organization_id=context.organization_id,
                action=AuditAction.CONTEXT_ASSEMBLED,
                entity_type="retrieval_query",
                entity_id=retrieved.query.id,
                actor_id=context.user_id,
                occurred_at=datetime.now(UTC),
                summary=(
                    f"Assembled {assembled.token_count} token(s) from "
                    f"{len(assembled.included)} chunk(s)."
                ),
                succeeded=True,
            )
        )
        return ContextOutput(retrieval=retrieved, context=assembled)

    async def _mark_included(self, retrieved: RetrievalOutput, assembled: AssembledContext) -> None:
        """Record which results actually reached the model.

        The distinction ``included_in_context`` captures: a chunk can rank
        third and still be cut by the token budget, and "the model never
        saw it" demands a bigger budget while "retrieval never found it"
        demands a better index. Conflating them sends people to fix the
        wrong thing.
        """
        # citation_map is label -> chunk key; this needs the inverse,
        # because the row being stamped is found by chunk id.
        labels = {chunk_key: label for label, chunk_key in assembled.citation_map.items()}
        included = set(assembled.included)
        for row in await self._results.list_for_query(retrieved.query.id):
            key = str(row.document_chunk_id)
            if key in included:
                row.included_in_context = True
                row.citation_label = labels.get(key)
                await self._results.update(row)

    # -- feedback -----------------------------------------------------------

    async def submit_feedback(
        self,
        context: AccessContext,
        query_id: UUID,
        *,
        verdict: FeedbackVerdict,
        chunk_id: UUID | None = None,
        rank: int | None = None,
        relevance: float | None = None,
        comment: str | None = None,
    ) -> RetrievalFeedback:
        """Record one human judgement about one retrieval.

        The ground truth every offline metric is computed against -- see
        :mod:`app.evaluation.metrics`. Without it precision and recall
        have nothing to be measured against and the service can only
        report how fast it was, not how right.

        Raises:
            NotFoundError: If the query is not in this organization.
            ValidationError: If *relevance* is outside ``[0, 1]``.
        """
        if relevance is not None and not 0.0 <= relevance <= 1.0:
            raise ValidationError(
                f"relevance must be within [0, 1], got {relevance!r}; nDCG treats it "
                "as a gain and a value outside that range distorts every score it "
                "contributes to."
            )
        query = await self._queries.require_in_org(context.organization_id, query_id)
        return await self._feedback.create(
            RetrievalFeedback(
                organization_id=context.organization_id,
                retrieval_query_id=query.id,
                document_chunk_id=chunk_id,
                verdict=verdict,
                rank=rank,
                relevance=relevance,
                comment=comment,
                submitted_by=context.user_id,
                submitted_at=datetime.now(UTC),
            )
        )

    # -- recording ------------------------------------------------------------

    async def _open_query(
        self,
        context: AccessContext,
        query_text: str,
        *,
        strategy: RetrievalStrategy,
        fusion_method: FusionMethod,
        top_k: int,
        metadata_filters: dict[str, str],
    ) -> RetrievalQuery:
        """Write the query row before running anything.

        Before, not after: a retrieval that crashes or times out is
        exactly the one worth having a record of, and a row written only
        on success records nothing about the failures.
        """
        filters: dict[str, object] = dict(metadata_filters)
        return await self._queries.create(
            RetrievalQuery(
                organization_id=context.organization_id,
                query_text=query_text[:8_000],
                normalized_query=_normalize(query_text),
                strategy=strategy,
                fusion_method=fusion_method,
                outcome=RetrievalOutcome.FAILED,
                top_k=top_k,
                requested_by=context.user_id,
                project_scope_id=next(iter(sorted(context.project_scope_ids)), None),
                caller_roles=sorted(context.roles),
                metadata_filters=filters,
                embedding_model=self._embeddings.model,
                executed_at=datetime.now(UTC),
            )
        )

    async def _close_query(
        self,
        record: RetrievalQuery,
        *,
        outcome: RetrievalOutcome,
        started: float,
        timings: Mapping[str, float] | None = None,
        output: RetrievalOutput | None = None,
        error: str | None = None,
    ) -> None:
        """Finalise the query row with its outcome and timings."""
        record.outcome = outcome
        record.duration_ms = (time.perf_counter() - started) * 1_000.0
        record.error = error[:2_000] if error else None
        if timings:
            record.embedding_ms = timings.get("embedding_ms")
            record.search_ms = timings.get("search_ms")
            record.rerank_ms = timings.get("rerank_ms")
        if output is not None:
            record.result_count = len(output.results)
            record.denied_count = output.denied
        await self._queries.update(record)

    @staticmethod
    def _outcome(output: RetrievalOutput) -> RetrievalOutcome:
        """Which outcome one retrieval earned.

        ``DENIED`` beats ``EMPTY`` when everything found was withheld: the
        two look identical to the caller and demand opposite responses --
        one is a permissions question, the other a coverage question.
        """
        if output.results:
            return RetrievalOutcome.SUCCEEDED
        if output.denied:
            return RetrievalOutcome.DENIED
        return RetrievalOutcome.EMPTY

    async def _persist_results(
        self,
        record: RetrievalQuery,
        output: RetrievalOutput,
        *,
        rerank_method: RerankMethod | None,
    ) -> None:
        """Write one row per result, and one per reranking decision."""
        for item in output.results:
            await self._results.create(
                RetrievalResult(
                    organization_id=record.organization_id,
                    retrieval_query_id=record.id,
                    document_id=item.document.id,
                    document_chunk_id=item.chunk.id,
                    rank=item.rank,
                    score=item.score,
                    vector_score=item.arm_scores.get(VECTOR_ARM),
                    keyword_score=item.arm_scores.get(KEYWORD_ARM),
                    graph_score=item.arm_scores.get(GRAPH_ARM),
                    vector_rank=item.arm_ranks.get(VECTOR_ARM),
                    keyword_rank=item.arm_ranks.get(KEYWORD_ARM),
                    graph_rank=item.arm_ranks.get(GRAPH_ARM),
                )
            )
            if rerank_method is None or item.rank == item.rank_before_rerank:
                continue
            await self._rerankings.create(
                RerankingResult(
                    organization_id=record.organization_id,
                    retrieval_query_id=record.id,
                    document_chunk_id=item.chunk.id,
                    method=rerank_method,
                    rank_before=item.rank_before_rerank,
                    rank_after=item.rank,
                    score_before=item.score_before_rerank,
                    score_after=item.score,
                )
            )


def _fusion_confidence(position: int, total: int) -> float:
    """Fusion rank as a scale-free relevance signal in ``[0, 1]``.

    Linear over the candidate list -- best gets 1.0, worst gets 0.0 --
    rather than a reciprocal decay, which would flatten everything below
    the top few into a tie and hand those positions back to the tiebreak
    signals this exists to outweigh. A single candidate gets 1.0: it is
    the best thing found, and dividing by zero to say so is not required.
    """
    if total <= 1:
        return 1.0
    return 1.0 - (position / (total - 1))


def _string_metadata(chunk: DocumentChunk) -> dict[str, str]:
    """The chunk's own metadata, flattened to strings for the reranker."""
    return {key: str(value) for key, value in chunk.chunk_metadata.items()}


def _to_context_chunk(item: RetrievedChunk) -> ContextChunk:
    """Bridge a retrieved chunk into the pure context assembler."""
    return ContextChunk(
        key=item.key,
        content=item.chunk.content,
        score=item.score,
        document_id=str(item.document.id),
        document_title=item.document.title,
        sequence=item.chunk.sequence,
        page_number=item.chunk.page_number,
        section_path=item.chunk.section_path,
        source_uri=item.document.source_uri,
    )


def _normalize(text: str) -> str:
    """Fold a query for grouping.

    Case and whitespace only. Stemming would group questions that are not
    the same question, and the point of this column is to count how often
    one thing was actually asked.
    """
    return " ".join(text.lower().split())[:1_000]


DEFAULT_ARM_WEIGHTS: dict[str, float] = {VECTOR_ARM: 0.6, KEYWORD_ARM: 0.3, GRAPH_ARM: 0.1}
"""Weights for score-based fusion when the caller names none.

Semantic search carries most of the load on the natural-language
questions this service is asked, the lexical arm exists to catch the
exact identifiers and error codes embeddings blur together, and the graph
arm contributes only where entities were linked at all. Reciprocal Rank
Fusion ignores these entirely -- it consumes ranks, not scores -- which
is exactly why it is the default method.
"""


def _default_weights(arms: Mapping[str, Sequence[RankedItem]]) -> dict[str, float]:
    """Weights covering the arms that actually ran, renormalised.

    Renormalised rather than passed through: a keyword-only search
    weighted 0.3 would produce fused scores a third of the size of the
    same search run as hybrid, and any threshold a caller set against one
    would be wrong against the other.
    """
    present = {name: DEFAULT_ARM_WEIGHTS.get(name, 1.0) for name in arms}
    total = sum(present.values()) or 1.0
    return {name: weight / total for name, weight in present.items()}


_ARMS_FOR_STRATEGY: dict[RetrievalStrategy, frozenset[str]] = {
    RetrievalStrategy.VECTOR: frozenset({VECTOR_ARM}),
    RetrievalStrategy.SEMANTIC: frozenset({VECTOR_ARM}),
    RetrievalStrategy.KEYWORD: frozenset({KEYWORD_ARM}),
    RetrievalStrategy.FUZZY: frozenset({KEYWORD_ARM}),
    RetrievalStrategy.BOOLEAN: frozenset({KEYWORD_ARM}),
    RetrievalStrategy.METADATA: frozenset({KEYWORD_ARM}),
    RetrievalStrategy.GRAPH: frozenset({GRAPH_ARM}),
    RetrievalStrategy.HYBRID: frozenset({VECTOR_ARM, KEYWORD_ARM, GRAPH_ARM}),
}
"""Which arms each strategy runs.

``FUZZY``, ``BOOLEAN``, and ``METADATA`` map onto the lexical arm rather
than getting bespoke implementations, and the mapping is stated here
rather than hidden: PostgreSQL's own text search already handles the
first two, and a metadata-only query is a filtered lexical lookup. Naming
them in this table is what keeps them from looking implemented when they
are aliases."""


__all__ = [
    "DEFAULT_ARM_WEIGHTS",
    "DEFAULT_CANDIDATE_MULTIPLIER",
    "DEFAULT_MIN_SIMILARITY",
    "GRAPH_ARM",
    "KEYWORD_ARM",
    "VECTOR_ARM",
    "ContextOutput",
    "RetrievalOutput",
    "RetrievalService",
    "RetrievedChunk",
]
