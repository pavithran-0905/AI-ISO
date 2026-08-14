"""Application factory.

Assembles the FastAPI application: configuration, logging, PostgreSQL,
Redis, events, notifications, telemetry, the JWT verification key,
middleware, exception handlers, routers, and background workers.

**All five background jobs are leader-elected.** Each is pure database
work with no per-replica state, so N replicas would be N times the load
for an identical result -- see :mod:`app.workers.registrar`.
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
from shared_core.security.cors import CorsConfig, development_cors_config, production_cors_config
from shared_core.telemetry.factory import create_telemetry_framework
from shared_core.validation.middleware import RequestValidationMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.cors import CORSMiddleware

from app.api import ALL_ROUTERS
from app.config.keys import load_public_key
from app.config.settings import Settings, get_settings
from app.services.notifications import EdgeNotifier, NotifyingPublisher
from app.types import EventPublisher
from app.workers.health_sweep import HealthSweepWorker
from app.workers.protocol_sweep import ProtocolSweepWorker
from app.workers.registrar import (
    register_health_sweep,
    register_protocol_sweep,
    register_statistics_rollup,
    register_synchronization_sweep,
    register_update_reconcile,
)
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.synchronization_sweep import SynchronizationSweepWorker
from app.workers.update_reconcile import UpdateReconcileWorker

logger = get_logger("app.startup")


async def _build_workers(
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    publish_event: EventPublisher,
    notifier: EdgeNotifier,
    settings: Settings,
) -> SchedulerManager | None:
    """Register and start the five leader-elected background jobs."""
    service = settings.service
    if not service.workers_enabled:
        logger.info("background workers are disabled by configuration")
        return None

    queue = await create_queue_framework(settings.rabbitmq)
    manager = create_scheduler_framework(
        queue.manager, redis_client, queue_name="edge_management_scheduler_queue"
    )
    register_health_sweep(
        manager,
        HealthSweepWorker(
            session_factory,
            publish_event=publish_event,
            notifier=notifier,
            degraded_threshold=service.health_degraded_component_threshold,
            unhealthy_threshold=service.health_unhealthy_component_threshold,
            stale_threshold_minutes=service.stale_device_threshold_minutes,
        ).run_job,
        interval_seconds=service.health_sweep_seconds,
    )
    register_synchronization_sweep(
        manager,
        SynchronizationSweepWorker(
            session_factory,
            publish_event=publish_event,
            notifier=notifier,
            stale_threshold_minutes=service.sync_stale_threshold_minutes,
        ).run_job,
        interval_seconds=service.synchronization_sweep_seconds,
    )
    register_update_reconcile(
        manager,
        UpdateReconcileWorker(
            session_factory,
            publish_event=publish_event,
            notifier=notifier,
            max_skew=service.max_supported_firmware_skew,
            stale_threshold_minutes=service.sync_stale_threshold_minutes,
        ).run_job,
        interval_seconds=service.update_reconcile_seconds,
    )
    register_protocol_sweep(
        manager,
        ProtocolSweepWorker(
            session_factory, stale_after_minutes=service.stale_device_threshold_minutes
        ).run_job,
        interval_seconds=service.protocol_sweep_seconds,
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
    notifier = EdgeNotifier(notification_manager)
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
        database.session_factory, cache.client, app.state.publish_event, notifier, settings
    )
    app.state.scheduler_manager = scheduler_manager

    logger.info(
        "edge-management-service starting up",
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
        logger.info("edge-management-service shutting down")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    configure_logging(
        service=settings.application.app_name,
        environment=settings.application.environment,
        level=settings.application.log_level,
    )

    app = FastAPI(
        title="AI-IOS Enterprise Edge Management Service",
        description=(
            "Site/device registration, zero-touch provisioning, health monitoring, "
            "offline-first synchronization, OTA updates, edge AI, and industrial "
            "protocol connectivity tracking across a distributed edge fleet. "
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
