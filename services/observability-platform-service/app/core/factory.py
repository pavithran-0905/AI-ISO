"""Application factory.

Assembles the FastAPI application: configuration, logging, PostgreSQL,
Redis, events, notifications, telemetry, the JWT verification key,
middleware, exception handlers, routers, and background workers.

**All five background jobs are leader-elected.** Each is pure database
work with no per-replica state, so N replicas would be N times the load
for an identical result -- see :mod:`app.workers.registrar`.

**Notifications wrap the event publisher, not the other way round.**
:class:`~app.services.notifications.NotifyingPublisher` forwards every
event to the real publisher unchanged and only additionally notifies for
the subset that warrant it, so every service built against
``app.state.publish_event`` gets notifications for free without knowing
notifications exist.
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
from shared_core.notifications.factory import create_notification_framework
from shared_core.queue.factory import create_queue_framework
from shared_core.scheduler import SchedulerManager
from shared_core.scheduler.factory import create_scheduler_framework
from shared_core.security.cors import (
    CorsConfig,
    development_cors_config,
    production_cors_config,
)
from shared_core.telemetry.factory import create_telemetry_framework
from shared_core.validation.middleware import RequestValidationMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.cors import CORSMiddleware

from app.api import ALL_ROUTERS
from app.config.keys import load_public_key
from app.config.settings import Settings, get_settings
from app.services.notifications import NotifyingPublisher, ObservabilityNotifier
from app.types import EventPublisher
from app.workers.anomaly_sweep import AnomalySweepWorker
from app.workers.registrar import (
    register_anomaly_sweep,
    register_retention_sweep,
    register_slo_evaluation,
    register_statistics_rollup,
    register_topology_rebuild,
)
from app.workers.retention_sweep import RetentionSweepWorker
from app.workers.slo_evaluation import SloEvaluationWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.topology_rebuild import TopologyRebuildWorker

logger = get_logger("app.startup")


async def _build_workers(
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    publish_event: EventPublisher,
    settings: Settings,
) -> SchedulerManager | None:
    """Register and start the five leader-elected background jobs."""
    service = settings.service
    if not service.workers_enabled:
        logger.info("background workers are disabled by configuration")
        return None

    queue = await create_queue_framework(settings.rabbitmq)
    manager = create_scheduler_framework(
        queue.manager, redis_client, queue_name="observability_platform_scheduler_queue"
    )
    register_slo_evaluation(
        manager,
        SloEvaluationWorker(session_factory, publish_event=publish_event).run_job,
        interval_seconds=service.slo_evaluation_seconds,
    )
    register_anomaly_sweep(
        manager,
        AnomalySweepWorker(session_factory, publish_event=publish_event).run_job,
        interval_seconds=service.anomaly_sweep_seconds,
    )
    register_topology_rebuild(
        manager,
        TopologyRebuildWorker(session_factory).run_job,
        interval_seconds=service.topology_rebuild_seconds,
    )
    register_retention_sweep(
        manager,
        RetentionSweepWorker(session_factory).run_job,
        interval_seconds=service.retention_sweep_seconds,
    )
    register_statistics_rollup(
        manager,
        StatisticsRollupWorker(session_factory).run_job,
        interval_seconds=service.statistics_rollup_seconds,
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

    notification_manager = create_notification_framework(email_settings=settings.email)
    notifier = ObservabilityNotifier(notification_manager)
    app.state.notifier = notifier
    app.state.publish_event = NotifyingPublisher(events.manager.publish, notifier)

    telemetry = create_telemetry_framework(
        settings.telemetry,
        service_version=settings.application.app_version,
        environment=settings.application.environment.value,
    )
    app.state.telemetry = telemetry

    app.state.jwt_public_key = load_public_key(settings.service.jwt_public_key_path)
    app.state.service_settings = settings.service

    scheduler_manager = await _build_workers(
        database.session_factory, cache.client, app.state.publish_event, settings
    )
    app.state.scheduler_manager = scheduler_manager

    logger.info(
        "observability-platform-service starting up",
        extra={
            "extra_fields": {
                "workers_enabled": settings.service.workers_enabled,
                "telemetry_enabled": settings.telemetry.telemetry_enabled,
            }
        },
    )
    try:
        yield
    finally:
        if scheduler_manager is not None:
            await scheduler_manager.stop()
        telemetry.tracer_provider.shutdown()
        await database.shutdown()
        await cache.shutdown()
        await events.shutdown()
        logger.info("observability-platform-service shutting down")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    configure_logging(
        service=settings.application.app_name,
        environment=settings.application.environment,
        level=settings.application.log_level,
    )

    app = FastAPI(
        title="AI-IOS Enterprise Observability Platform Service",
        description=(
            "Metrics, logs, traces, events and profiles at platform scale, with "
            "deterministic SLO/error-budget tracking, robust-statistics anomaly "
            "detection, capacity forecasting with honest prediction intervals, "
            "root cause analysis that never claims causation it did not earn, "
            "and cost analytics that keeps unattributed spend visible rather than "
            "averaged away. No commercial observability SaaS, no black-box AI "
            "scoring -- every finding here can be explained and reproduced. See "
            "this package's own README."
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
