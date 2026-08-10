"""SQLAlchemy models for the RAG service.

Every model is imported here so ``BaseModel.metadata`` is fully
populated before Alembic autogenerate or ``create_all`` runs -- a model
in a module nobody imported is a table that silently does not exist.
"""

from __future__ import annotations

from app.models.analytics import (
    IndexingJob,
    KnowledgeSource,
    RagAudit,
    RagReport,
    RagStatistic,
)
from app.models.document import Document, DocumentChunk, DocumentMetadata, DocumentVersion
from app.models.embedding import (
    EMBEDDING_DIMENSIONS,
    EmbeddingModel,
    EmbeddingVector,
    VectorIndex,
)
from app.models.retrieval import (
    RerankingResult,
    RetrievalFeedback,
    RetrievalQuery,
    RetrievalResult,
)

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "Document",
    "DocumentChunk",
    "DocumentMetadata",
    "DocumentVersion",
    "EmbeddingModel",
    "EmbeddingVector",
    "IndexingJob",
    "KnowledgeSource",
    "RagAudit",
    "RagReport",
    "RagStatistic",
    "RerankingResult",
    "RetrievalFeedback",
    "RetrievalQuery",
    "RetrievalResult",
    "VectorIndex",
]
