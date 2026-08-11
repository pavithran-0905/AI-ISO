"""Repositories for the RAG service."""

from __future__ import annotations

from app.repositories.analytics import (
    IndexingJobRepository,
    KnowledgeSourceRepository,
    RagAuditRepository,
    RagReportRepository,
    RagStatisticRepository,
)
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import (
    EmbeddingModelRepository,
    EmbeddingVectorRepository,
    VectorIndexRepository,
)
from app.repositories.retrieval import (
    RerankingResultRepository,
    RetrievalFeedbackRepository,
    RetrievalQueryRepository,
    RetrievalResultRepository,
)

__all__ = [
    "DocumentChunkRepository",
    "DocumentMetadataRepository",
    "DocumentRepository",
    "DocumentVersionRepository",
    "EmbeddingModelRepository",
    "EmbeddingVectorRepository",
    "IndexingJobRepository",
    "KnowledgeSourceRepository",
    "RagAuditRepository",
    "RagReportRepository",
    "RagStatisticRepository",
    "RerankingResultRepository",
    "RetrievalFeedbackRepository",
    "RetrievalQueryRepository",
    "RetrievalResultRepository",
    "VectorIndexRepository",
]
