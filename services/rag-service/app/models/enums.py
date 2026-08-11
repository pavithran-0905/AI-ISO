"""Every closed vocabulary this service stores.

Each enum here maps onto a list docs/062 names literally. Where the spec
lists a capability rather than a state -- "Upload", "Import", "Parse" are
*transitions*, not resting states a document can be found in -- it is
modelled as an operation, not an enum member, for the same reason
prompt-management-service does not have a ``ROLLBACK`` lifecycle status.

Stored as ``String`` columns rather than PostgreSQL ``ENUM`` types, per
the convention every AI-IOS service follows: a native enum needs a
migration to add a member, and these vocabularies grow.
"""

from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """The knowledge source types docs/062's own "KNOWLEDGE SOURCES" names.

    Split between *file formats* a document arrives in and *systems* a
    document is pulled from, because they behave differently: a format
    needs a parser, a system needs a connector plus credentials plus a
    sync strategy.
    """

    # File formats -- each has a parser in app/parsers/.
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    # Systems -- each needs a connector, credentials, and a sync strategy.
    REST_API = "rest_api"
    GIT_REPOSITORY = "git_repository"
    CONFLUENCE = "confluence"
    SHAREPOINT = "sharepoint"
    OBJECT_STORAGE = "object_storage"
    NEO4J = "neo4j"
    POSTGRESQL = "postgresql"
    CUSTOM = "custom"


class DocumentStatus(StrEnum):
    """One document's own resting state.

    ``Upload``, ``Import``, ``Parse``, ``Normalize``, ``Chunk``,
    ``Embed``, ``Index``, ``Restore``, and ``Delete`` from docs/062's
    "DOCUMENT LIFECYCLE" are transitions, not states -- a document is
    never *found* in "parse". They are operations on these states, and
    where one can fail mid-way that failure is a state: ``FAILED``.
    """

    PENDING = "pending"
    """Stored but not yet parsed. The state an upload lands in."""
    PARSED = "parsed"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    """Retrievable. The only state ``retrieve`` will draw from."""
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"
    DELETED = "deleted"
    """Soft-deleted, so ``Restore`` has something to restore. A hard
    delete would make the spec's own ``Restore`` unimplementable."""


class ClassificationLevel(StrEnum):
    """Document sensitivity ("ACCESS CONTROL": Classification Levels).

    Ordered least to most restrictive. :func:`classification_rank` is the
    comparison to use -- a ``StrEnum`` compares alphabetically, which
    would put ``CONFIDENTIAL`` below ``INTERNAL``.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


_CLASSIFICATION_ORDER: tuple[ClassificationLevel, ...] = (
    ClassificationLevel.PUBLIC,
    ClassificationLevel.INTERNAL,
    ClassificationLevel.CONFIDENTIAL,
    ClassificationLevel.RESTRICTED,
    ClassificationLevel.SECRET,
)


def classification_rank(level: ClassificationLevel | str) -> int:
    """How restrictive *level* is, as a comparable integer.

    Needed because these are ``StrEnum`` members and ``<`` on them is
    alphabetical: ``"confidential" < "internal"`` is true as a string
    comparison and false as a sensitivity comparison. Getting that
    backwards in an access check would disclose the more sensitive
    document, so the ordering is explicit rather than incidental.

    Raises:
        ValueError: If *level* is not a known classification.
    """
    try:
        return _CLASSIFICATION_ORDER.index(ClassificationLevel(str(level)))
    except ValueError as exc:
        raise ValueError(f"Unknown classification level {level!r}.") from exc


class ChunkStrategy(StrEnum):
    """The chunking strategies docs/062's own "CHUNKING STRATEGIES" names."""

    FIXED_SIZE = "fixed_size"
    SLIDING_WINDOW = "sliding_window"
    SEMANTIC = "semantic"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    CODE_AWARE = "code_aware"
    TABLE_AWARE = "table_aware"
    HYBRID = "hybrid"


class ChunkKind(StrEnum):
    """What a chunk's own content actually is.

    Kept apart from :class:`ChunkStrategy`, which is *how* the chunk was
    produced. A table extracted by ``TABLE_AWARE`` and a table that
    happened to fall inside a ``FIXED_SIZE`` window are both tables, and
    a reranker that weights prose against tables needs to know which is
    which regardless of how the split was made.
    """

    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    CODE = "code"
    LIST = "list"
    METADATA = "metadata"
    CAPTION = "caption"


class EmbeddingProvider(StrEnum):
    """The embedding providers docs/062's own "EMBEDDING MODELS" names.

    ``BUILTIN`` is this service's own offline feature-hashing encoder. It
    is not in the spec's list and is deliberately added: without it, no
    part of ingestion or retrieval could be exercised without a
    credential, which would mean the service's own tests do not run.

    Named ``BUILTIN`` rather than ``LOCAL`` on purpose -- ``LOCAL``
    already means "a self-hosted OpenAI-compatible endpoint" elsewhere in
    this platform, which is a network call with a credential.
    """

    BUILTIN = "builtin"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    VOYAGE = "voyage"
    COHERE = "cohere"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    BGE = "bge"
    E5 = "e5"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class VectorStoreProvider(StrEnum):
    """The vector backends docs/062's own "VECTOR DATABASE" names.

    Only ``PGVECTOR`` and ``MEMORY`` have implementations here, and that
    is stated rather than disguised: the compose stack runs
    ``pgvector/pgvector:pg17`` and nothing else, so a Qdrant or Pinecone
    client in this repository would be code that has never once been run
    against the thing it claims to talk to. The pluggable architecture
    the spec asks for is the point -- see
    :mod:`app.vector_store.registry` for exactly what a new provider has
    to implement.

    ``MEMORY`` is not in the spec's list. It exists so the abstraction
    itself is testable independently of PostgreSQL.
    """

    PGVECTOR = "pgvector"
    MEMORY = "memory"
    QDRANT = "qdrant"
    MILVUS = "milvus"
    WEAVIATE = "weaviate"
    CHROMA = "chroma"
    PINECONE = "pinecone"
    REDIS_VECTOR = "redis_vector"
    FAISS = "faiss"


class IndexKind(StrEnum):
    """The indexing modes docs/062's own "INDEXING" section names."""

    FULL = "full"
    INCREMENTAL = "incremental"
    REALTIME = "realtime"
    BATCH = "batch"
    SCHEDULED = "scheduled"
    PRIORITY = "priority"


class IndexStatus(StrEnum):
    """One indexing job's own state."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    """Some documents indexed, some failed. Distinct from ``FAILED``
    because the successfully indexed ones are retrievable and must not be
    re-indexed, and distinct from ``COMPLETED`` because something still
    needs attention."""


class RetrievalStrategy(StrEnum):
    """How one query searched ("HYBRID SEARCH")."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    BM25 = "bm25"
    GRAPH = "graph"
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    FUZZY = "fuzzy"
    BOOLEAN = "boolean"
    METADATA = "metadata"


class FusionMethod(StrEnum):
    """How multiple ranked lists were combined into one.

    ``RRF`` is the default and the honest one: cosine similarity, BM25
    scores, and graph relevance are not on a comparable scale, so adding
    them directly makes whichever happens to have the largest numeric
    range dominate. Reciprocal Rank Fusion uses only the *ranks*.
    ``WEIGHTED_SCORE`` is offered because the spec names "Weighted
    Scoring", and it normalises each list before weighting.
    """

    RRF = "rrf"
    WEIGHTED_SCORE = "weighted_score"
    MAX_SCORE = "max_score"


class RerankMethod(StrEnum):
    """The reranking approaches docs/062's own "RERANKING" names.

    ``CROSS_ENCODER`` is declared but unimplemented -- it needs a model
    this service does not ship and cannot download at import time. The
    others are real: they are deterministic functions of data already on
    the chunk row, which is why they can be tested exactly.
    """

    METADATA = "metadata"
    FRESHNESS = "freshness"
    ACCESS_PRIORITY = "access_priority"
    CONFIDENCE = "confidence"
    DIVERSITY = "diversity"
    HYBRID = "hybrid"
    CROSS_ENCODER = "cross_encoder"
    LLM = "llm"


class RetrievalOutcome(StrEnum):
    """Whether one retrieval produced anything usable."""

    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    """Ran correctly and matched nothing. Distinct from ``FAILED``: an
    empty result is a fact about the corpus, not an error, and conflating
    them makes "is retrieval broken?" unanswerable."""
    FAILED = "failed"
    DENIED = "denied"
    """Matches existed but the caller could not see them. Recorded
    separately so an access-control problem is not mistaken for a
    coverage problem."""


class FeedbackVerdict(StrEnum):
    """Human feedback on one retrieval ("EVALUATION": Human Feedback)."""

    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    OUTDATED = "outdated"
    DUPLICATE = "duplicate"


class EvaluationMetric(StrEnum):
    """The retrieval metrics docs/062's own "EVALUATION" section names."""

    PRECISION = "precision"
    RECALL = "recall"
    MRR = "mrr"
    NDCG = "ndcg"
    HIT_RATE = "hit_rate"
    LATENCY = "latency"
    CITATION_ACCURACY = "citation_accuracy"
    HALLUCINATION_RISK = "hallucination_risk"
    GROUNDING = "grounding"


class SyncStatus(StrEnum):
    """One knowledge source's own last sync outcome."""

    NEVER_SYNCED = "never_synced"
    SYNCING = "syncing"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    """The source was reached and some of its documents imported. Its own
    status, not a flavour of ``SUCCEEDED``, for the same reason
    :attr:`IndexStatus.PARTIAL` is: a sync where eight of ten documents
    landed reads as done if it is recorded as success, and the two that
    did not land are then invisible until somebody goes looking for a
    document that was never imported."""
    FAILED = "failed"
    UNREACHABLE = "unreachable"
    """The source itself could not be contacted, as distinct from a sync
    that reached it and then failed. Only one of those is worth paging
    someone about."""
    CONFLICT = "conflict"


class SecurityFinding(StrEnum):
    """What an ingestion scan detected.

    A document is untrusted input that ends up inside a model prompt, so
    indirect prompt injection is the finding that matters most here --
    the attack where the payload is in the *retrieved* text rather than
    the user's own message.
    """

    SECRET_DETECTED = "secret_detected"
    PII_DETECTED = "pii_detected"
    PROMPT_INJECTION = "prompt_injection"
    UNSAFE_CONTENT = "unsafe_content"
    OVERSIZED = "oversized"
    PARSE_FAILURE = "parse_failure"
    ENCODING_ANOMALY = "encoding_anomaly"


class SecuritySeverity(StrEnum):
    """How serious one finding is."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportKind(StrEnum):
    """The report kinds docs/062's own "REPORTING" section names."""

    INDEX = "index"
    RETRIEVAL = "retrieval"
    KNOWLEDGE_SOURCE = "knowledge_source"
    EMBEDDING = "embedding"
    ACCURACY = "accuracy"
    EVALUATION = "evaluation"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    """How a report's content is rendered."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"


class ReportStatus(StrEnum):
    """One report generation's own state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(StrEnum):
    """What an audit row records (docs/062's own "AUDIT" section)."""

    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_IMPORTED = "document_imported"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_ARCHIVED = "document_archived"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_RESTORED = "document_restored"
    INDEXED = "indexed"
    REINDEXED = "reindexed"
    INDEX_OPTIMIZED = "index_optimized"
    RETRIEVAL_EXECUTED = "retrieval_executed"
    RETRIEVAL_DENIED = "retrieval_denied"
    CONTEXT_ASSEMBLED = "context_assembled"
    PERMISSION_CHANGED = "permission_changed"
    SOURCE_CREATED = "source_created"
    SOURCE_UPDATED = "source_updated"
    SOURCE_SYNCED = "source_synced"
    EMBEDDING_GENERATED = "embedding_generated"
    EVALUATION_COMPLETED = "evaluation_completed"
    SECURITY_SCANNED = "security_scanned"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "AuditAction",
    "ChunkKind",
    "ChunkStrategy",
    "ClassificationLevel",
    "DocumentStatus",
    "EmbeddingProvider",
    "EvaluationMetric",
    "FeedbackVerdict",
    "FusionMethod",
    "IndexKind",
    "IndexStatus",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "RerankMethod",
    "RetrievalOutcome",
    "RetrievalStrategy",
    "SecurityFinding",
    "SecuritySeverity",
    "SourceKind",
    "SyncStatus",
    "VectorStoreProvider",
    "classification_rank",
]
