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
from app.services.notifications import NotifyingPublisher, SdkCliNotifier
from app.workers.cli_update_check_sweep import CliUpdateCheckSweepWorker
from app.workers.plugin_update_sweep import PluginUpdateSweepWorker
from app.workers.registrar import (
    register_cli_update_check_sweep,
    register_plugin_update_sweep,
    register_session_expiry_sweep,
    register_statistics_rollup,
    register_version_compatibility_sweep,
)
from app.workers.session_expiry_sweep import SessionExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.version_compatibility_sweep import VersionCompatibilitySweepWorker

logger = get_logger("app.startup")


async def _build_workers(
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    notifier: SdkCliNotifier,
    settings: Settings,
) -> SchedulerManager | None:
    """Register and start the five leader-elected background jobs."""
    service = settings.service
    if not service.workers_enabled:
        logger.info("background workers are disabled by configuration")
        return None

    queue = await create_queue_framework(settings.rabbitmq)
    manager = create_scheduler_framework(
        queue.manager, redis_client, queue_name="sdk_cli_scheduler_queue"
    )
    register_version_compatibility_sweep(
        manager,
        VersionCompatibilitySweepWorker(
            session_factory,
            notifier=notifier,
            sdk_warning_days_before=service.sdk_deprecation_warning_days_before,
            cli_warning_days_before=service.cli_deprecation_warning_days_before,
        ).run_job,
        interval_seconds=service.version_compatibility_sweep_seconds,
    )
    register_cli_update_check_sweep(
        manager,
        CliUpdateCheckSweepWorker(session_factory, notifier=notifier).run_job,
        interval_seconds=service.cli_update_check_sweep_seconds,
    )
    register_plugin_update_sweep(
        manager,
        PluginUpdateSweepWorker(session_factory, notifier=notifier).run_job,
        interval_seconds=service.plugin_update_sweep_seconds,
    )
    register_session_expiry_sweep(
        manager,
        SessionExpirySweepWorker(session_factory).run_job,
        interval_seconds=service.session_expiry_sweep_seconds,
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
    notifier = SdkCliNotifier(notification_manager)
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
        database.session_factory, cache.client, notifier, settings
    )
    app.state.scheduler_manager = scheduler_manager

    logger.info(
        "sdk-cli-service starting up",
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
        logger.info("sdk-cli-service shutting down")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    configure_logging(
        service=settings.application.app_name,
        environment=settings.application.environment,
        level=settings.application.log_level,
    )

    app = FastAPI(
        title="AI-IOS Enterprise SDK & CLI Service",
        description=(
            "Generating, maintaining, versioning, documenting, and distributing official SDKs "
            "and a cross-platform CLI for every AI-IOS capability. See this package's own README."
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
