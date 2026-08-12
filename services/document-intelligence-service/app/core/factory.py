"""Application factory.

Assembles the FastAPI application: configuration, logging, PostgreSQL,
Redis, events, the OCR engine, notifications, the JWT verification key,
middleware, exception handlers, routers, background workers, and Prometheus
instrumentation.

**The parser registry is populated by importing the format modules.** That
import is here, and it is not decorative: each module calls ``register()``
at import time, and a process that never imported them serves a service
whose every upload fails with "no parser registered" for formats it
demonstrably supports.

**The OCR engine is probed at startup, not on first use.** A deployment
without the Tesseract binary should say so in its startup log, not
discover it on the first scanned document an hour later -- and it must
still start, because every other format works without it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
from shared_core.security.cors import (
    CorsConfig,
    development_cors_config,
    production_cors_config,
)
from shared_core.storage.client import create_minio_client
from shared_core.storage.wrapper import StorageWrapper
from shared_core.validation.middleware import RequestValidationMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.cors import CORSMiddleware

from app.api import ALL_ROUTERS
from app.classification.classifier import ClassifierConfig
from app.config.keys import load_public_key
from app.config.settings import Settings, get_settings
from app.documents import binary_formats, text_formats  # noqa: F401  (registers parsers)
from app.forms.extractor import FormConfig
from app.layout.analyzer import LayoutConfig
from app.ocr.engine import TesseractEngine
from app.services.pipeline import PipelineConfig
from app.services.storage import DocumentStorage
from app.tables.extractor import TableConfig
from app.types import EventPublisher
from app.validation.engine import ValidationConfig
from app.workers.processing_sweep import ProcessingSweepWorker
from app.workers.registrar import (
    register_processing_sweep,
    register_retention_sweep,
    register_review_expiry_sweep,
    register_statistics_rollup,
)
from app.workers.retention_sweep import RetentionSweepWorker
from app.workers.review_expiry_sweep import ReviewExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker

logger = get_logger("app.startup")


def _build_pipeline_config(settings: Settings) -> PipelineConfig:
    """One pipeline configuration for the process.

    Built from settings once at startup rather than per request: every
    threshold here is a deployment decision, and rebuilding the config on
    each request would let two requests in the same deployment disagree
    about what counts as low confidence.
    """
    service = settings.service
    return PipelineConfig(
        review_below_confidence=service.review_required_below_confidence,
        ocr_minimum_confidence=service.ocr_minimum_confidence,
        classifier=ClassifierConfig(minimum_confidence=service.classification_minimum_confidence),
        layout=LayoutConfig(),
        tables=TableConfig(minimum_confidence=service.table_minimum_confidence),
        forms=FormConfig(minimum_confidence=service.form_minimum_confidence),
        validation=ValidationConfig(
            confidence_threshold=service.review_required_below_confidence,
            completeness_target=service.validation_minimum_completeness,
            duplicate_similarity=service.duplicate_similarity_threshold,
        ),
    )


def _build_ocr_engine(settings: Settings) -> object | None:
    """The OCR engine, or ``None`` when OCR cannot run here.

    ``None`` rather than an engine that returns empty text: a stub would
    make every scanned document look successfully read and empty, which is
    the one failure this service must never produce silently. The pipeline
    treats ``None`` as a reason to send the document to review.
    """
    service = settings.service
    if not service.ocr_enabled:
        logger.info("OCR is disabled by configuration")
        return None

    engine = TesseractEngine(
        timeout_seconds=service.ocr_timeout_seconds,
        minimum_confidence=service.ocr_minimum_confidence,
    )
    availability = engine.probe()
    if not availability.available:
        logger.warning(
            "OCR is enabled but unavailable; scanned documents will be routed to review",
            extra={"extra_fields": {"reason": availability.reason}},
        )
        return None
    logger.info(
        "OCR engine ready",
        extra={"extra_fields": {"engine": "tesseract", "detail": availability.reason}},
    )
    return engine


async def _build_storage(settings: Settings) -> DocumentStorage | None:
    """The document object store, or ``None`` if it cannot be reached.

    ``None`` rather than a failed startup: the service still serves reads,
    listings, reviews and reports without it. What it cannot do is
    *process* a document, and the endpoints that need bytes say exactly
    that instead of returning an empty result.
    """
    try:
        wrapper = StorageWrapper(create_minio_client(settings.minio))
        storage = DocumentStorage(wrapper, bucket=settings.service.storage_bucket)
        await storage.ensure_ready()
    except Exception as error:
        logger.warning(
            "document object storage is unavailable; documents can be listed but " "not processed",
            extra={"extra_fields": {"error": str(error)}},
        )
        return None
    logger.info(
        "document object storage ready",
        extra={"extra_fields": {"bucket": storage.bucket}},
    )
    return storage


async def _build_workers(
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    publish_event: EventPublisher,
    pipeline_config: PipelineConfig,
    ocr_engine: object | None,
    storage: DocumentStorage | None,
    settings: Settings,
) -> SchedulerManager | None:
    """Register and start the leader-elected background jobs.

    All four are leader-elected. Each is pure database work with no
    per-replica state, so N replicas would be N times the load for an
    identical result -- and two replicas running the same processing sweep
    would OCR the same scan twice, which on a paid OCR backend costs real
    money.
    """
    service = settings.service
    if not service.workers_enabled:
        logger.info("background workers are disabled by configuration")
        return None

    queue = await create_queue_framework(settings.rabbitmq)
    manager = create_scheduler_framework(
        queue.manager,
        redis_client,
        queue_name="document_intelligence_scheduler_queue",
    )
    register_processing_sweep(
        manager,
        ProcessingSweepWorker(
            session_factory,
            publish_event=publish_event,
            config=pipeline_config,
            ocr_engine=ocr_engine,
            storage=storage,
        ).run_job,
        interval_seconds=service.processing_sweep_seconds,
    )
    register_review_expiry_sweep(
        manager,
        ReviewExpirySweepWorker(session_factory, publish_event=publish_event).run_job,
        interval_seconds=service.review_expiry_sweep_seconds,
    )
    register_statistics_rollup(
        manager,
        StatisticsRollupWorker(session_factory).run_job,
        interval_seconds=service.statistics_rollup_seconds,
    )
    register_retention_sweep(
        manager,
        RetentionSweepWorker(session_factory, publish_event=publish_event).run_job,
        interval_seconds=service.retention_sweep_seconds,
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
    app.state.pipeline_config = _build_pipeline_config(settings)
    app.state.ocr_engine = _build_ocr_engine(settings)
    app.state.notifications = None
    app.state.storage = await _build_storage(settings)

    scheduler_manager = await _build_workers(
        database.session_factory,
        cache.client,
        events.manager.publish,
        app.state.pipeline_config,
        app.state.ocr_engine,
        app.state.storage,
        settings,
    )
    app.state.scheduler_manager = scheduler_manager

    from app.documents.parser import supported_formats  # noqa: PLC0415

    logger.info(
        "document-intelligence-service starting up",
        extra={
            "extra_fields": {
                "workers_enabled": settings.service.workers_enabled,
                "parsers": [str(fmt) for fmt in supported_formats()],
                "ocr_available": app.state.ocr_engine is not None,
                "storage_available": app.state.storage is not None,
                "max_document_bytes": settings.service.max_document_bytes,
                "review_below_confidence": (settings.service.review_required_below_confidence),
                "translation_enabled": settings.service.translation_enabled,
            }
        },
    )
    try:
        yield
    finally:
        if scheduler_manager is not None:
            await scheduler_manager.stop()
        await database.shutdown()
        await cache.shutdown()
        await events.shutdown()
        logger.info("document-intelligence-service shutting down")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    configure_logging(
        service=settings.application.app_name,
        environment=settings.application.environment,
        level=settings.application.log_level,
    )

    app = FastAPI(
        title="AI-IOS Enterprise Document Intelligence Service",
        description=(
            "Document ingestion across fourteen formats, OCR with per-page "
            "confidence, layout analysis, multi-label classification, entity "
            "and table and form extraction, extractive summarization, "
            "translation with terminology preservation, seven kinds of "
            "validation, human review with corrections stored beside the "
            "originals, analytics and reports, and an immutable audit trail. "
            "See this package's own README."
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
