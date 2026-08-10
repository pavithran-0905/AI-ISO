"""RAG service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, the
embedding provider and model, vector-store selection, chunking and
retrieval defaults, GraphRAG connectivity, indexing limits, and the
worker intervals.

**This service does have an embedding provider credential**, unlike
prompt-management-service. Embedding *is* one of its jobs. But it ships
with a provider that needs no credential at all -- see
:mod:`app.embeddings.encoder` -- so the whole ingestion and retrieval
path is exercisable, testable, and live-verifiable on a machine with no
API key and no network. That is deliberate: a RAG service whose tests
only run when someone has an OpenAI key is a RAG service whose tests do
not run.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from shared_core.config.cache import get_settings as get_shared_settings
from shared_core.config.settings import (
    ApplicationSettings,
    DatabaseSettings,
    EmailSettings,
    MinioSettings,
    Neo4jSettings,
    RabbitMQSettings,
    RedisSettings,
)


class RagServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_RAG_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8033, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- platform integrations this service reaches live -------------------

    knowledge_graph_service_base_url: str = Field(default="http://localhost:8019")
    prompt_management_service_base_url: str = Field(default="http://localhost:8032")
    notification_center_base_url: str = Field(default="http://localhost:8025")
    integration_hub_service_base_url: str = Field(default="http://localhost:8029")

    http_client_timeout_seconds: float = Field(default=30.0, gt=0)

    # ---- embeddings --------------------------------------------------------

    embedding_provider: str = Field(default="builtin")
    """Which provider generates vectors. ``builtin`` is the offline
    feature-hashing encoder and needs no credential; every other value
    names a real HTTP provider and requires ``embedding_api_key``."""
    embedding_model: str = Field(default="builtin-hashing")
    embedding_dimensions: int = Field(default=1536, ge=8, le=4_096)
    """Must match the ``vector(N)`` column width. Changing it invalidates
    every stored vector, which is why the column width is fixed in the
    migration and this is validated against it at startup rather than
    trusted."""
    embedding_api_key: str = Field(default="")
    embedding_base_url: str = Field(default="")
    embedding_batch_size: int = Field(default=64, ge=1, le=2_048)
    """How many chunks go into one provider call. Larger batches cost
    fewer round trips; too large and a single failure loses more work."""
    embedding_cache_enabled: bool = Field(default=True)
    embedding_cache_ttl_seconds: int = Field(default=604_800, ge=1)
    """A week. An embedding is a pure function of (text, model), so it
    never goes stale on its own -- the TTL exists to bound cache size,
    not to protect freshness."""
    embedding_usd_per_1k_tokens: float = Field(default=0.00002, ge=0)

    # ---- chunking ----------------------------------------------------------

    default_chunk_size: int = Field(default=1_000, ge=32, le=32_000)
    default_chunk_overlap: int = Field(default=150, ge=0, le=8_000)
    max_chunks_per_document: int = Field(default=10_000, ge=1)
    """A ceiling, not a target. One pathological upload should not be
    able to generate a million embedding calls."""

    # ---- retrieval ---------------------------------------------------------

    default_top_k: int = Field(default=10, ge=1, le=500)
    max_top_k: int = Field(default=200, ge=1, le=2_000)
    vector_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    graph_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    """Hybrid ranking weights. They do not have to sum to 1 -- the fuser
    normalises -- but keeping them close to it makes the numbers
    readable in a retrieval_queries row."""
    rrf_k: int = Field(default=60, ge=1)
    """Reciprocal Rank Fusion's smoothing constant. 60 is the value from
    the original TREC work and the one ai-assistant-service already
    uses; keeping them equal means a query answered by either service
    ranks the same way."""
    max_context_tokens: int = Field(default=8_000, ge=64, le=1_000_000)
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    """Chunks below this cosine similarity are dropped before reranking.
    Zero by default: a hard floor tuned on one corpus silently returns
    nothing on another."""

    # ---- vector store ------------------------------------------------------

    vector_store: str = Field(default="pgvector")
    """Which backend holds the vectors. ``pgvector`` and ``memory`` are
    implemented; see :mod:`app.vector_store.registry` for what adding
    another one requires."""

    # ---- graph rag ---------------------------------------------------------

    graph_rag_enabled: bool = Field(default=True)
    graph_max_depth: int = Field(default=2, ge=1, le=6)
    """Relationship expansion depth. Beyond two hops a knowledge graph
    of any size returns most of itself, which is the opposite of
    retrieval."""
    graph_max_nodes: int = Field(default=100, ge=1, le=10_000)

    # ---- indexing ----------------------------------------------------------

    max_document_bytes: int = Field(default=52_428_800, ge=1)
    """50 MiB. Parsing is done in memory, so this is the real limit on
    what one upload can cost."""
    indexing_batch_size: int = Field(default=25, ge=1, le=1_000)

    # ---- security ----------------------------------------------------------

    injection_scanning_enabled: bool = Field(default=True)
    """Scan ingested text for prompt-injection patterns. A document is
    untrusted input that ends up inside a model prompt, which is exactly
    the indirect-injection path this has to defend."""
    block_ingestion_on_injection: bool = Field(default=False)
    """Off by default: a false positive that refuses a legitimate
    document is worse than a flagged one a human reviews, and the
    finding is recorded either way."""
    redact_pii_on_ingestion: bool = Field(default=True)

    # ---- workers -----------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    indexing_sweep_seconds: int = Field(default=30, ge=5, le=3_600)
    source_sync_sweep_seconds: int = Field(default=900, ge=30, le=86_400)
    statistics_rollup_seconds: int = Field(default=900, ge=60, le=86_400)
    index_optimization_seconds: int = Field(default=3_600, ge=60, le=604_800)


@dataclass(frozen=True, slots=True)
class Settings:
    """Every configuration section this service actually uses."""

    application: ApplicationSettings
    database: DatabaseSettings
    redis: RedisSettings
    rabbitmq: RabbitMQSettings
    email: EmailSettings
    neo4j: Neo4jSettings
    minio: MinioSettings
    service: RagServiceSettings


def build_settings(*, service: RagServiceSettings | None = None) -> Settings:
    """Build a :class:`Settings`, reusing the shared aggregate's current values."""
    shared = get_shared_settings()
    return Settings(
        application=shared.application,
        database=shared.database,
        redis=shared.redis,
        rabbitmq=shared.rabbitmq,
        email=shared.email,
        neo4j=shared.neo4j,
        minio=shared.minio,
        service=service if service is not None else RagServiceSettings(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide cached settings, built once."""
    return build_settings()


__all__ = ["RagServiceSettings", "Settings", "build_settings", "get_settings"]
