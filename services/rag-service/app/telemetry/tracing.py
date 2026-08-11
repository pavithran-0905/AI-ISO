"""RAG telemetry (docs/062 "TELEMETRY"): Document Ingestion, Chunking,
Embedding, Vector Search, Reranking, Context Assembly, Retrieval Quality.

Integrates ``shared_core.telemetry`` (Prompt 024).

**Every call below passes attributes via ``**{...}``, never a literal
``attributes={...}`` keyword.** ``start_span``'s own signature is
``start_span(tracer, name, *, span_type=None, **attributes)`` -- there is
no parameter actually named ``attributes``, only that catch-all. Passing
one anyway silently drops every attribute onto the floor instead of
raising, a confirmed repo-wide defect in AI-IOS services built before
Prompt 054. This copy was written correct from the start.

**Spans carry identifiers, counts, and scores -- never document text,
chunk content, query text, or assembled context.** A document body can be
a tenant's confidential material, a query can name a person, and an
assembled context is both at once. A tracing backend has different
retention and access rules than this service's own database, and a span is
the easiest place in a platform to accidentally publish a corpus.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import Span, Tracer
from shared_core.telemetry.span import SpanType, start_span


@contextmanager
def trace_ingestion(
    tracer: Tracer, *, source_kind: str, byte_size: int, **attributes: object
) -> Iterator[Span]:
    """Span one document ingestion ("Document Ingestion").

    The source kind and byte size, never the filename: a filename is
    frequently the most identifying thing about a document, and it is not
    needed to see how ingestion is performing by format and size.
    """
    with start_span(
        tracer,
        "rag.ingest",
        span_type=SpanType.WORKFLOW_STEP,
        **{"rag.source_kind": source_kind, "rag.byte_size": byte_size, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_chunking(
    tracer: Tracer, *, strategy: str, chunk_count: int, **attributes: object
) -> Iterator[Span]:
    """Span one chunking pass ("Chunking")."""
    with start_span(
        tracer,
        "rag.chunk",
        span_type=SpanType.WORKFLOW_STEP,
        **{"rag.chunk_strategy": strategy, "rag.chunk_count": chunk_count, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_embedding(
    tracer: Tracer, *, provider: str, model: str, batch_size: int, **attributes: object
) -> Iterator[Span]:
    """Span one embedding batch ("Embedding").

    Typed as an AI request because that is what it is for every provider
    but the builtin one -- so its latency and its failures land in the
    same bucket as the platform's other model calls rather than in this
    service's own compute time.
    """
    with start_span(
        tracer,
        "rag.embed",
        span_type=SpanType.AI_REQUEST,
        **{
            "rag.embedding_provider": provider,
            "rag.embedding_model": model,
            "rag.batch_size": batch_size,
            **attributes,
        },
    ) as span:
        yield span


@contextmanager
def trace_vector_search(
    tracer: Tracer, *, provider: str, top_k: int, **attributes: object
) -> Iterator[Span]:
    """Span one similarity search ("Vector Search")."""
    with start_span(
        tracer,
        "rag.vector_search",
        span_type=SpanType.DATABASE_QUERY,
        **{"rag.vector_store": provider, "rag.top_k": top_k, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_keyword_search(
    tracer: Tracer, *, candidates: int, **attributes: object
) -> Iterator[Span]:
    """Span the lexical arm of hybrid search."""
    with start_span(
        tracer,
        "rag.keyword_search",
        span_type=SpanType.DATABASE_QUERY,
        **{"rag.candidates": candidates, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_fusion(tracer: Tracer, *, method: str, arms: int, **attributes: object) -> Iterator[Span]:
    """Span one fusion of the retrieval arms ("Hybrid Search")."""
    with start_span(
        tracer,
        "rag.fuse",
        span_type=SpanType.WORKFLOW_STEP,
        **{"rag.fusion_method": method, "rag.arms": arms, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_reranking(
    tracer: Tracer, *, method: str, candidates: int, **attributes: object
) -> Iterator[Span]:
    """Span one reranking pass ("Reranking").

    Worth its own span because a reranker that changes nothing is pure
    added latency, and that is only visible if its time is attributed
    separately from the search that fed it.
    """
    with start_span(
        tracer,
        "rag.rerank",
        span_type=SpanType.WORKFLOW_STEP,
        **{"rag.rerank_method": method, "rag.candidates": candidates, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_context_assembly(
    tracer: Tracer, *, budget: int, included: int, **attributes: object
) -> Iterator[Span]:
    """Span one context assembly ("Context Assembly")."""
    with start_span(
        tracer,
        "rag.assemble_context",
        span_type=SpanType.WORKFLOW_STEP,
        **{"rag.token_budget": budget, "rag.chunks_included": included, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_retrieval(
    tracer: Tracer, *, strategy: str, top_k: int, **attributes: object
) -> Iterator[Span]:
    """Span one whole retrieval, end to end ("Retrieval Quality")."""
    with start_span(
        tracer,
        "rag.retrieve",
        span_type=SpanType.WORKFLOW_STEP,
        **{"rag.strategy": strategy, "rag.top_k": top_k, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_indexing_job(
    tracer: Tracer, *, kind: str, documents: int, **attributes: object
) -> Iterator[Span]:
    """Span one indexing job ("Indexing Pipeline")."""
    with start_span(
        tracer,
        "rag.index_job",
        span_type=SpanType.BACKGROUND_JOB,
        **{"rag.index_kind": kind, "rag.documents": documents, **attributes},
    ) as span:
        yield span


__all__ = [
    "trace_chunking",
    "trace_context_assembly",
    "trace_embedding",
    "trace_fusion",
    "trace_indexing_job",
    "trace_ingestion",
    "trace_keyword_search",
    "trace_reranking",
    "trace_retrieval",
    "trace_vector_search",
]
