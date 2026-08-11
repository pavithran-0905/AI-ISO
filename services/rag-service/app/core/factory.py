"""Application factory.

Assembles the FastAPI application: configuration, logging, PostgreSQL,
Redis, events, the outbound HTTP client, the embedding service, the
GraphRAG driver, the JWT verification key, middleware, exception handlers,
routers, background workers, and Prometheus instrumentation.

**The embedding service and the GraphRAG driver are process-wide; the
vector store is not.** The first two own connection pools and a cache that
would be thrown away on every request. The store reads and writes through
a database session, so one held across requests would be writing into a
transaction that has already been committed -- see
:func:`~app.api.deps.get_vector_store`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from shared_core.cache.factory import create_cache_framework
from shared_core.cache.settings import CacheSettings
from shared_core.database.factory import create_database_framework
from shared_core.events.factory import create_event_framework
from shared_core.exceptions import register_exception_handlers
from shared_core.logging import configure_logging, get_logger
from shared_core.middleware import (
    LocalizationMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from shared_core.queue.factory import create_queue_framework
from shared_core.scheduler import SchedulerManager
from shared_core.scheduler.factory import create_scheduler_framework
from shared_core.security.cors import CorsConfig, development_cors_config, production_cors_config
from shared_core.validation.middleware import RequestValidationMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.cors import CORSMiddleware

from app.api import ALL_ROUTERS
from app.config.keys import load_public_key
from app.config.settings import Settings, get_settings
from app.embeddings.client import build_client
from app.embeddings.encoder import HashingEncoder
from app.embeddings.service import EmbeddingService
from app.graph_rag.client import GraphClient, create_driver
from app.graph_rag.retriever import GraphRetriever
from app.models.enums import EmbeddingProvider
from app.types import EventPublisher
from app.workers.document_expiry_sweep import DocumentExpirySweepWorker
from app.workers.indexing_sweep import IndexingSweepWorker
from app.workers.registrar import (
    register_document_expiry_sweep,
    register_indexing_sweep,
    register_source_sync_sweep,
    register_statistics_rollup,
)
from app.workers.source_sync_sweep import SourceSyncSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker

logger = get_logger("app.startup")


def _build_embeddings(
    http_client: httpx.AsyncClient, redis_client: Redis, settings: Settings
) -> EmbeddingService:
    """Build the process-wide embedding service.

    The cache is Redis-backed and shared across replicas, because an
    embedding is a pure function of ``(text, model)``: a vector one replica
    paid for is the correct answer for every other replica, and a
    per-process cache would pay for the same text once per replica.
    """
    service = settings.service
    provider = EmbeddingProvider(service.embedding_provider)
    client = build_client(
        http_client,
        provider=provider,
        base_url=service.embedding_base_url,
        api_key=service.embedding_api_key,
    )
    return EmbeddingService(
        provider=provider,
        model=service.embedding_model,
        dimensions=service.embedding_dimensions,
        client=client,
        encoder=HashingEncoder(dimensions=service.embedding_dimensions) if client is None else None,
        cache=_VectorCache(redis_client) if service.embedding_cache_enabled else None,
        batch_size=service.embedding_batch_size,
        cache_ttl_seconds=service.embedding_cache_ttl_seconds,
        usd_per_1k_tokens=service.embedding_usd_per_1k_tokens,
    )


class _VectorCache:
    """Adapts Redis to the embedding service's own tiny cache protocol.

    Deliberately not the full cache manager: the embedding service needs
    exactly ``get`` and ``set`` with a TTL, and depending on a richer
    interface would couple embedding to cache-framework features it does
    not use.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        value = await self._client.get(key)
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else str(value)

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        if ttl_seconds:
            await self._client.setex(key, ttl_seconds, value)
        else:
            await self._client.set(key, value)


def _build_graph(settings: Settings) -> GraphRetriever | None:
    """Build the GraphRAG retriever, or ``None`` when it is disabled.

    ``None`` rather than a disabled retriever object, so the graph arm is
    absent from the code path rather than present and silently returning
    nothing -- which is much harder to tell apart from a graph that simply
    knows nothing about the query.
    """
    service = settings.service
    if not service.graph_rag_enabled:
        return None
    driver = create_driver(settings.neo4j, enabled=True)
    return GraphRetriever(
        GraphClient(driver, enabled=True),
        max_depth=service.graph_max_depth,
        max_nodes=service.graph_max_nodes,
    )


async def _build_workers(
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    publish_event: EventPublisher,
    embeddings: EmbeddingService,
    settings: Settings,
) -> SchedulerManager | None:
    """Register and start the leader-elected background jobs.

    All four are leader-elected. Each is pure database work with no
    per-replica state, so N replicas would be N times the load for an
    identical result -- and two replicas running the same indexing job
    would embed its documents twice and be billed twice, which is the one
    failure here that costs real money.
    """
    if not settings.service.workers_enabled:
        return None

    queue = await create_queue_framework(settings.rabbitmq)
    manager = create_scheduler_framework(
        queue.manager, redis_client, queue_name="rag_service_scheduler_queue"
    )
    register_indexing_sweep(
        manager,
        IndexingSweepWorker(
            session_factory,
            embeddings=embeddings,
            publish_event=publish_event,
            vector_store=settings.service.vector_store,
            batch_size=settings.service.indexing_batch_size,
        ).run_job,
        interval_seconds=settings.service.indexing_sweep_seconds,
    )
    register_source_sync_sweep(
        manager,
        SourceSyncSweepWorker(session_factory, publish_event=publish_event).run_job,
        interval_seconds=settings.service.source_sync_sweep_seconds,
    )
    register_document_expiry_sweep(
        manager,
        DocumentExpirySweepWorker(session_factory, publish_event=publish_event).run_job,
        interval_seconds=settings.service.index_optimization_seconds,
    )
    register_statistics_rollup(
        manager,
        StatisticsRollupWorker(
            session_factory,
            publish_event=publish_event,
            window_seconds=settings.service.statistics_rollup_seconds,
            embedding_dimensions=settings.service.embedding_dimensions,
        ).run_job,
        interval_seconds=settings.service.statistics_rollup_seconds,
    )
    await manager.start()
    return manager


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    database = await create_database_framework(settings.database)
    app.state.db_engine = database.engine
    app.state.db_session_factory = database.session_factory

    cache = await create_cache_framework(CacheSettings(redis=settings.redis))
    app.state.cache_manager = cache.manager
    app.state.redis_client = cache.client

    events = await create_event_framework(settings.rabbitmq)
    app.state.publish_event = events.manager.publish

    app.state.jwt_public_key = load_public_key(settings.service.jwt_public_key_path)
    app.state.service_settings = settings.service

    app.state.http_client = httpx.AsyncClient(timeout=settings.service.http_client_timeout_seconds)
    app.state.embeddings = _build_embeddings(app.state.http_client, cache.client, settings)
    app.state.graph_retriever = _build_graph(settings)

    scheduler_manager = await _build_workers(
        database.session_factory,
        cache.client,
        events.manager.publish,
        app.state.embeddings,
        settings,
    )
    app.state.scheduler_manager = scheduler_manager

    logger.info(
        "rag-service starting up",
        extra={
            "extra_fields": {
                "workers_enabled": settings.service.workers_enabled,
                "embedding_provider": settings.service.embedding_provider,
                "embedding_model": settings.service.embedding_model,
                "embedding_dimensions": settings.service.embedding_dimensions,
                "vector_store": settings.service.vector_store,
                "graph_rag_enabled": settings.service.graph_rag_enabled,
                "min_similarity": settings.service.min_similarity,
                "injection_scanning_enabled": settings.service.injection_scanning_enabled,
            }
        },
    )
    try:
        yield
    finally:
        if scheduler_manager is not None:
            await scheduler_manager.stop()
        graph = app.state.graph_retriever
        if graph is not None:
            await graph.close()
        await app.state.http_client.aclose()
        await database.shutdown()
        await cache.shutdown()
        await events.shutdown()
        logger.info("rag-service shutting down")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    configure_logging(
        service=settings.application.app_name,
        environment=settings.application.environment,
        level=settings.application.log_level,
    )

    app = FastAPI(
        title="AI-IOS Enterprise RAG Service",
        description=(
            "Document ingestion and parsing, nine chunking strategies, "
            "pluggable embeddings and vector stores, hybrid search with "
            "reciprocal rank fusion, reranking, GraphRAG expansion, "
            "token-budgeted context assembly with citations, retrieval "
            "evaluation against human feedback, knowledge-source "
            "management, analytics, and an immutable audit trail. See this "
            "package's own README."
        ),
        version=settings.application.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    cors_config = _build_cors_config(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_config.allow_origins),
        allow_methods=list(cors_config.allow_methods),
        allow_headers=list(cors_config.allow_headers),
        allow_credentials=cors_config.allow_credentials,
        max_age=cors_config.max_age_seconds,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(LocalizationMiddleware)
    app.add_middleware(RequestValidationMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)

    for router in ALL_ROUTERS:
        app.include_router(router)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

    return app


def _build_cors_config(settings: Settings) -> CorsConfig:
    """Build the CORS policy for the current environment."""
    if settings.application.environment.value == "production":
        return production_cors_config(settings.service.cors_allowed_origins)
    return development_cors_config()


__all__ = ["create_app"]
