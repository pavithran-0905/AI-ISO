"""The health sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Runs a real database latency check and a real Redis ping for every
organization with at least one tenant, classifying and recording both
as a diagnostic run and the component's latest health-check reading.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from redis.asyncio import Redis
from shared_core.database.health import check_database_health
from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.diagnostics.engine import classify_latency_status
from app.models.enums import DiagnosticCategory, HealthCheckStatus
from app.services.bundle import build_repositories
from app.services.diagnostics import DiagnosticsService
from app.types import EventPublisher

logger = get_logger("app.workers.health_sweep")


class HealthSweepWorker:
    """Checks database and cache latency for every organization and
    records both a diagnostic run and a health-check reading."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        db_engine: AsyncEngine,
        redis_client: Redis,
        publish_event: EventPublisher,
        warning_ms: float,
        critical_ms: float,
    ) -> None:
        self._session_factory = session_factory
        self._db_engine = db_engine
        self._redis_client = redis_client
        self._publish_event = publish_event
        self._warning_ms = warning_ms
        self._critical_ms = critical_ms

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def _check_cache_latency_ms(self) -> float | None:
        start = time.monotonic()
        try:
            await self._redis_client.ping()
        except Exception:
            return None
        return (time.monotonic() - start) * 1000

    async def tick(self) -> int:
        """Check every organization's dependencies, returning how many
        were checked."""
        now = datetime.now(UTC)
        checked = 0

        _db_status, db_latency_ms = await check_database_health(self._db_engine)
        cache_latency_ms = await self._check_cache_latency_ms()

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = DiagnosticsService(
                repos.diagnostics, repos.health_checks, publish=self._publish_event
            )

            for organization_id in await repos.tenants.list_organization_ids():
                await service.run_diagnostic(
                    organization_id,
                    category=DiagnosticCategory.DATABASE,
                    latency_ms=db_latency_ms,
                    warning_ms=self._warning_ms,
                    critical_ms=self._critical_ms,
                    now=now,
                )
                await service.record_health_check(
                    organization_id,
                    component="database",
                    status=classify_latency_status(
                        db_latency_ms, warning_ms=self._warning_ms, critical_ms=self._critical_ms
                    ),
                    now=now,
                )

                cache_status = (
                    HealthCheckStatus.UNHEALTHY
                    if cache_latency_ms is None
                    else classify_latency_status(
                        cache_latency_ms, warning_ms=self._warning_ms, critical_ms=self._critical_ms
                    )
                )
                await service.run_diagnostic(
                    organization_id,
                    category=DiagnosticCategory.CACHE,
                    latency_ms=cache_latency_ms,
                    warning_ms=self._warning_ms,
                    critical_ms=self._critical_ms,
                    now=now,
                )
                await service.record_health_check(
                    organization_id, component="cache", status=cache_status, now=now
                )
                checked += 1
            await session.commit()

        logger.info("health sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["HealthSweepWorker"]
