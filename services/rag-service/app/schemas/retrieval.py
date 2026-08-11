"""Request and response schemas for search, retrieval, and context.

**The caller's access scope is never taken from the request body.** Roles
and clearance come from the Bearer token, resolved in
:mod:`app.api.deps`. A body field for them would let any caller name any
clearance, which is not an access control -- it is a form asking people
to be honest.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    FeedbackVerdict,
    FusionMethod,
    RerankMethod,
    RetrievalOutcome,
    RetrievalStrategy,
)


class SearchRequest(BaseModel):
    """``POST /rag/search`` -- ranked chunks, no context assembly."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=8_000)
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    fusion_method: FusionMethod = FusionMethod.RRF
    rerank_method: RerankMethod | None = RerankMethod.HYBRID
    """``null`` skips reranking and keeps fusion order -- what a cheap
    lexical lookup wants."""
    top_k: int = Field(default=10, ge=1, le=200)
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata_filters: dict[str, str] = Field(default_factory=dict, max_length=32)
    document_ids: list[UUID] = Field(default_factory=list, max_length=200)
    weights: dict[str, float] | None = Field(default=None, max_length=8)


class RetrieveRequest(SearchRequest):
    """``POST /rag/retrieve`` -- the same search, with citations resolved.

    Identical inputs to ``/rag/search`` on purpose: the difference is what
    comes back, not what goes in, so a caller moving between them does not
    have to rewrite the request.
    """


class ContextRequest(SearchRequest):
    """``POST /rag/context`` -- retrieve and assemble a token-budgeted block."""

    max_tokens: int = Field(default=4_000, ge=1, le=200_000)
    include_citations: bool = True
    allow_partial: bool = False
    """Truncate the first chunk that does not fit rather than skipping it.
    Off by default: a chunk cut mid-sentence can change what it appears to
    say, and a model has no way to know it is reading a fragment."""


class CitationResponse(BaseModel):
    """One citation, rendered and resolvable."""

    label: str
    chunk_key: str
    document_id: str
    document_title: str
    page_number: int | None = None
    section_path: str | None = None
    source_uri: str | None = None
    score: float = 0.0
    rendered: str


class SearchHitResponse(BaseModel):
    """One ranked result."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    rank: int
    score: float
    content: str
    page_number: int | None = None
    section_path: str | None = None
    heading: str | None = None
    arm_scores: dict[str, float] = Field(default_factory=dict)
    arm_ranks: dict[str, int] = Field(default_factory=dict)
    """Per-arm scores and ranks, so "why did this rank third?" has an
    answer. A fused score with nothing behind it is unauditable."""


class RetrievalResponse(BaseModel):
    """What one search or retrieval produced."""

    query_id: UUID
    query: str
    strategy: RetrievalStrategy
    outcome: RetrievalOutcome
    results: list[SearchHitResponse] = Field(default_factory=list)
    candidates: int = 0
    denied: int = 0
    """How many matches the caller was not allowed to see. Non-zero with
    no results is an access-control answer, not a coverage answer, and the
    two demand opposite responses."""
    duration_ms: float = 0.0
    embedding_ms: float | None = None
    search_ms: float | None = None
    rerank_ms: float | None = None


class ContextResponse(BaseModel):
    """An assembled context block, with what it left out."""

    query_id: UUID
    text: str
    citations: list[CitationResponse] = Field(default_factory=list)
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    duplicates_dropped: int = 0
    token_count: int = 0
    budget: int = 0
    truncated: bool = False
    retrieval: RetrievalResponse


class FeedbackRequest(BaseModel):
    """``POST /rag/retrieve/{query_id}/feedback`` -- one human judgement.

    The ground truth every offline metric is measured against. Without it
    the service can report how fast it was, never how right.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: FeedbackVerdict
    chunk_id: UUID | None = None
    rank: int | None = Field(default=None, ge=1)
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    comment: str | None = Field(default=None, max_length=4_000)


class FeedbackResponse(BaseModel):
    """One recorded judgement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    retrieval_query_id: UUID
    document_chunk_id: UUID | None
    verdict: FeedbackVerdict
    rank: int | None
    relevance: float | None
    comment: str | None
    submitted_by: str | None
    submitted_at: datetime


class MetricResponse(BaseModel):
    """One metric's value and what it was computed over."""

    name: str
    value: float
    considered: int
    relevant_total: int = 0
    measurable: bool = True
    """``False`` where nothing could be measured. Distinguished from a
    genuine zero because one says retrieval failed and the other says
    nobody has judged it yet."""


class EvaluationResponse(BaseModel):
    """An evaluation run's averaged metrics."""

    queries_evaluated: int = 0
    measurable: bool = False
    metrics: dict[str, float] = Field(default_factory=dict)
    unmeasurable: list[str] = Field(default_factory=list)


__all__ = [
    "CitationResponse",
    "ContextRequest",
    "ContextResponse",
    "EvaluationResponse",
    "FeedbackRequest",
    "FeedbackResponse",
    "MetricResponse",
    "RetrievalResponse",
    "RetrieveRequest",
    "SearchHitResponse",
    "SearchRequest",
]
