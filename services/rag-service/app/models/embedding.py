"""``embedding_models``, ``embedding_vectors``, and ``vector_indexes``.

**The vector column has a fixed width, and that is not an implementation
detail.** pgvector's ``vector(N)`` is a typed column: rows of different
dimensionality cannot coexist in it. Since a corpus embedded with two
different models is unrankable anyway -- cosine distances from different
embedding spaces are not comparable numbers -- the fixed width enforces
in the schema something that would otherwise be a silent correctness bug
producing plausible, wrong rankings.

Switching embedding models therefore means re-embedding. That is stated
here rather than discovered later; see :class:`EmbeddingModel`, whose
rows record which models a corpus has actually been embedded under.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import EmbeddingProvider, VectorStoreProvider

EMBEDDING_DIMENSIONS = 1536
"""The stored vector width, matching ``AIConstants.EMBEDDING_DIMENSIONS``
and ai-assistant-service's own ``AiEmbedding``. Keeping the two services
on one width means a corpus embedded by either is readable by the other.
"""


class EmbeddingModel(BaseModel):
    """``embedding_models`` -- one embedding model this organization uses.

    Registered rather than inferred, because the interesting questions
    are about the model as a *thing with a lifecycle*: which model is
    current, what did the previous one cost, how many vectors are still
    stored under a model nobody uses any more.
    """

    __tablename__ = "embedding_models"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provider", "model_name", "model_version", name="uq_embedding_model"
        ),
        Index("ix_embedding_model_default", "is_default"),
    )

    provider: Mapped[EmbeddingProvider] = mapped_column(String(24), index=True)
    model_name: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str] = mapped_column(String(64), default="1")
    """Part of the natural key ("EMBEDDING MODELS": Model Versioning). A
    provider silently updating a model behind the same name changes the
    embedding space, so a version bump is how that becomes visible rather
    than a mysterious drop in retrieval quality."""
    dimensions: Mapped[int] = mapped_column(Integer, default=EMBEDDING_DIMENSIONS)
    max_input_tokens: Mapped[int] = mapped_column(Integer, default=8_192)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usd_per_1k_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_embedded: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    model_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class EmbeddingVector(BaseModel):
    """``embedding_vectors`` -- one chunk's vector under one model.

    A chunk can have several: one per model it has been embedded under.
    That is what makes a model migration survivable -- the new vectors
    are written alongside the old ones, retrieval is switched over once
    the new set is complete, and only then are the old ones dropped.
    Overwriting in place would mean retrieval degrades continuously
    throughout the migration.
    """

    __tablename__ = "embedding_vectors"
    __table_args__ = (
        UniqueConstraint(
            "document_chunk_id", "provider", "model_name", name="uq_embedding_vector_chunk_model"
        ),
        Index("ix_embedding_vector_model", "model_name"),
        Index("ix_embedding_vector_document", "document_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[EmbeddingProvider] = mapped_column(String(24))
    model_name: Mapped[str] = mapped_column(String(128), index=True)
    dimensions: Mapped[int] = mapped_column(Integer, default=EMBEDDING_DIMENSIONS)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    """The pgvector column. Queried with ``<=>`` (cosine distance), which
    is what :class:`~app.vector_store.pgvector_store.PgVectorStore` uses
    -- pushing the ordering and the limit into SQL rather than loading
    every vector into Python, which is the difference between a query
    that scales and one that does not."""
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    """SHA-256 of the exact text embedded. An embedding is a pure
    function of (text, model), so this is both the cache key and the
    proof that a stored vector still corresponds to its chunk's current
    text -- a chunk edited without re-embedding is detectable rather
    than silently stale."""
    embedded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VectorIndex(BaseModel):
    """``vector_indexes`` -- one declared index over a set of vectors.

    Records what index exists where, under which provider and model, so
    "Index Validation" and "Index Optimization" have something concrete
    to act on. The row is the *declaration*; whether the backend has
    actually built it is answered by
    :meth:`~app.vector_store.base.VectorStore.describe`.
    """

    __tablename__ = "vector_indexes"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_vector_index_name"),
        Index("ix_vector_index_provider", "store_provider"),
    )

    name: Mapped[str] = mapped_column(String(128))
    store_provider: Mapped[VectorStoreProvider] = mapped_column(
        String(24), default=VectorStoreProvider.PGVECTOR, index=True
    )
    embedding_provider: Mapped[EmbeddingProvider] = mapped_column(String(24))
    model_name: Mapped[str] = mapped_column(String(128))
    dimensions: Mapped[int] = mapped_column(Integer, default=EMBEDDING_DIMENSIONS)
    metric: Mapped[str] = mapped_column(String(16), default="cosine")
    index_method: Mapped[str | None] = mapped_column(String(32), default=None)
    """``hnsw``, ``ivfflat``, or ``None`` for an exact sequential scan.
    ``None`` is the honest default: an approximate index built over too
    few rows is slower *and* less accurate than the scan it replaces, so
    one is created deliberately at a known size rather than up front."""
    index_parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    last_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    validation_error: Mapped[str | None] = mapped_column(Text, default=None)


__all__ = ["EMBEDDING_DIMENSIONS", "EmbeddingModel", "EmbeddingVector", "VectorIndex"]
