"""``retrieval_queries``, ``retrieval_results``, ``retrieval_feedback``,
and ``reranking_results``.

**Every retrieval is recorded, including the ones that returned nothing.**
An empty result is a fact about coverage, not an error, and a service
that only logs successful retrievals cannot answer "what are people
asking that we have no documents for?" -- which is the single most
actionable question a knowledge platform can answer.

The four tables separate what a query *asked*, what it *returned*, how
the returns were *reordered*, and what a human *thought of them*. Folding
those together would make the natural join -- "for queries where a human
said irrelevant, what did the reranker do?" -- impossible.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    FeedbackVerdict,
    FusionMethod,
    RerankMethod,
    RetrievalOutcome,
    RetrievalStrategy,
)


class RetrievalQuery(BaseModel):
    """``retrieval_queries`` -- one retrieval request, as asked.

    The query text is stored. That is a deliberate privacy decision with
    a real cost: search queries are sensitive, and this table will
    accumulate them. It is stored anyway because retrieval quality is
    unimprovable without it -- you cannot tune what you cannot see -- and
    the mitigation is that PII redaction runs over the text before it
    lands here, the rows are organization-scoped like everything else,
    and retention is the deployment's to configure.
    """

    __tablename__ = "retrieval_queries"
    __table_args__ = (
        Index("ix_retrieval_query_outcome", "outcome"),
        Index("ix_retrieval_query_executed_at", "executed_at"),
        Index("ix_retrieval_query_strategy", "strategy"),
    )

    query_text: Mapped[str] = mapped_column(Text)
    normalized_query: Mapped[str | None] = mapped_column(Text, default=None)
    """Lower-cased and whitespace-collapsed, so "Restore Backup" and
    "restore   backup" aggregate as one question in the analytics."""
    strategy: Mapped[RetrievalStrategy] = mapped_column(
        String(16), default=RetrievalStrategy.HYBRID, index=True
    )
    fusion_method: Mapped[FusionMethod | None] = mapped_column(String(16), default=None)
    outcome: Mapped[RetrievalOutcome] = mapped_column(
        String(16), default=RetrievalOutcome.SUCCEEDED, index=True
    )
    top_k: Mapped[int] = mapped_column(Integer, default=10)
    requested_by: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    project_scope_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    caller_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    """The roles the retrieval was performed under. Recorded because
    "why did this user not see that document?" is otherwise
    unanswerable after the fact -- the answer depends on state that has
    since changed."""
    metadata_filters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    """How many chunks matched before top-k truncation. The ratio to
    ``result_count`` is what says whether ``top_k`` is throwing away
    good answers."""
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    denied_count: Mapped[int] = mapped_column(Integer, default=0)
    """Matches the caller was not allowed to see. Non-zero with
    ``result_count`` zero is an access-control answer, not a coverage
    answer, and the two demand opposite responses."""
    vector_weight: Mapped[float] = mapped_column(Float, default=0.0)
    keyword_weight: Mapped[float] = mapped_column(Float, default=0.0)
    graph_weight: Mapped[float] = mapped_column(Float, default=0.0)
    embedding_model: Mapped[str | None] = mapped_column(String(128), default=None)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    embedding_ms: Mapped[float | None] = mapped_column(Float, default=None)
    search_ms: Mapped[float | None] = mapped_column(Float, default=None)
    rerank_ms: Mapped[float | None] = mapped_column(Float, default=None)
    """Timing split three ways because they have different remedies: a
    slow embed is a provider problem, a slow search is an index problem,
    a slow rerank is a top-k problem."""
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class RetrievalResult(BaseModel):
    """``retrieval_results`` -- one chunk returned by one query.

    Carries the scores as they were *at the time*, not as they would be
    recomputed now. Reranking weights change, documents change, models
    change; a stored score is the only record of why this chunk ranked
    where it did, and recomputing it later would answer a different
    question than the one being asked.
    """

    __tablename__ = "retrieval_results"
    __table_args__ = (
        Index("ix_retrieval_result_query_rank", "retrieval_query_id", "rank"),
        Index("ix_retrieval_result_chunk", "document_chunk_id"),
    )

    retrieval_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_queries.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    """Final position, 1-based. 1-based because a citation reads "[1]"
    and an off-by-one between the stored rank and the rendered citation
    is the kind of bug nobody notices until an auditor does."""
    score: Mapped[float] = mapped_column(Float, default=0.0)
    vector_score: Mapped[float | None] = mapped_column(Float, default=None)
    keyword_score: Mapped[float | None] = mapped_column(Float, default=None)
    graph_score: Mapped[float | None] = mapped_column(Float, default=None)
    vector_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    keyword_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    graph_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    """The per-strategy ranks Reciprocal Rank Fusion actually consumed.
    Stored so a fused score can be re-derived and checked; a fused score
    with no ranks behind it is unauditable."""
    included_in_context: Mapped[bool] = mapped_column(Boolean, default=False)
    """Whether it survived token budgeting. A chunk can rank third and
    still be cut, and "the model never saw it" is a different failure
    from "retrieval never found it"."""
    citation_label: Mapped[str | None] = mapped_column(String(64), default=None)


class RerankingResult(BaseModel):
    """``reranking_results`` -- how one reranker moved one chunk.

    Recorded per chunk per method, so the effect of a reranker is
    measurable rather than assumed. ``rank_before``/``rank_after`` is the
    whole point: a reranker that never changes an order is costing
    latency for nothing, and one that reorders wildly is worth
    scrutinising before it is trusted.
    """

    __tablename__ = "reranking_results"
    __table_args__ = (
        Index("ix_reranking_result_query", "retrieval_query_id"),
        Index("ix_reranking_result_method", "method"),
    )

    retrieval_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_queries.id", ondelete="CASCADE"), index=True
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[RerankMethod] = mapped_column(String(24), index=True)
    rank_before: Mapped[int] = mapped_column(Integer)
    rank_after: Mapped[int] = mapped_column(Integer)
    score_before: Mapped[float] = mapped_column(Float, default=0.0)
    score_after: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    rationale: Mapped[str | None] = mapped_column(Text, default=None)
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)


class RetrievalFeedback(BaseModel):
    """``retrieval_feedback`` -- what a human thought of one result.

    The ground truth every offline metric in :mod:`app.evaluation` is
    computed against. Without it, precision and recall have nothing to be
    precise or complete *about*, and the evaluation framework grades
    retrieval against its own opinion.
    """

    __tablename__ = "retrieval_feedback"
    __table_args__ = (
        Index("ix_retrieval_feedback_verdict", "verdict"),
        Index("ix_retrieval_feedback_query", "retrieval_query_id"),
    )

    retrieval_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_queries.id", ondelete="CASCADE"), index=True
    )
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), default=None, index=True
    )
    """``SET NULL`` rather than ``CASCADE``: feedback saying "this result
    was irrelevant" stays meaningful after the chunk is deleted, and
    deleting the evidence that a document was unhelpful because the
    document was removed would erase exactly the record explaining why."""
    verdict: Mapped[FeedbackVerdict] = mapped_column(String(24), index=True)
    rank: Mapped[int | None] = mapped_column(Integer, default=None)
    relevance: Mapped[float | None] = mapped_column(Float, default=None)
    """Graded relevance in ``[0, 1]`` where supplied. nDCG needs a graded
    signal; precision and recall only need the binary verdict."""
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    submitted_by: Mapped[str | None] = mapped_column(String(128), default=None)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = ["RerankingResult", "RetrievalFeedback", "RetrievalQuery", "RetrievalResult"]
