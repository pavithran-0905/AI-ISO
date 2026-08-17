"""The production readiness sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Publishes ``ProductionReady`` when an organization's aggregate
production readiness score (the same computation
``GET /production-readiness`` returns live -- see
``app.services.production_readiness``) clears the configured
threshold. **Edge-triggered via the most recent of its own four
underlying signal timestamps** (the latest hardening result,
compliance evaluation, operational readiness check, or disaster
recovery check): only organizations with at least one signal newer
than the lookback window are re-evaluated at all, the same "nothing
new happened, nothing to re-announce" discipline every other
edge-triggered worker in this codebase uses -- docs/079's own
DATABASE TABLES section has no dedicated readiness-state table to
track a transition against directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.domain_events import ProductionReadyEvent
from app.services.bundle import Repositories, build_repositories
from app.services.production_readiness import ProductionReadinessService
from app.types import EventPublisher

logger = get_logger("app.workers.production_readiness_sweep")

_SOURCE_SERVICE = "production-hardening-framework"


class ProductionReadinessSweepWorker:
    """Publishes ``ProductionReady`` for organizations whose recently
    updated signals now clear the readiness threshold."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher,
        threshold: float,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._threshold = threshold
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Re-evaluate every organization with recently updated
        readiness signals, returning how many were found ready."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        ready_count = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = ProductionReadinessService(repos)

            organization_ids: set[UUID] = set()
            organization_ids.update(await repos.hardening_runs.list_organization_ids())
            organization_ids.update(await repos.compliance_results.list_organization_ids())
            organization_ids.update(await repos.production_certifications.list_organization_ids())

            for organization_id in organization_ids:
                if not await self._has_recent_signal(repos, organization_id, lookback_cutoff):
                    continue

                result = await service.compute(organization_id, threshold=self._threshold)
                if not result.is_ready:
                    continue

                await self._publish(
                    ProductionReadyEvent(
                        source_service=_SOURCE_SERVICE,
                        organization_id=organization_id,
                        payload={"organization_id": str(organization_id), "score": result.score},
                    )
                )
                ready_count += 1

        logger.info(
            "production readiness sweep completed", extra={"extra_fields": {"ready": ready_count}}
        )
        return ready_count

    @staticmethod
    async def _has_recent_signal(
        repos: Repositories, organization_id: UUID, lookback_cutoff: datetime
    ) -> bool:
        """Whether any of the four readiness signal sources has a
        record newer than *lookback_cutoff*."""
        latest_hardening = await repos.hardening_results.list_recent(organization_id, limit=1)
        if latest_hardening and latest_hardening[0].created_at >= lookback_cutoff:
            return True
        latest_compliance = await repos.compliance_results.list_all(organization_id, limit=1)
        if latest_compliance and latest_compliance[0].evaluated_at >= lookback_cutoff:
            return True
        latest_operational = await repos.operational_readiness.list_all(organization_id, limit=1)
        if latest_operational and latest_operational[0].checked_at >= lookback_cutoff:
            return True
        latest_dr = await repos.disaster_recovery_checks.list_all(organization_id, limit=1)
        return bool(latest_dr and latest_dr[0].checked_at >= lookback_cutoff)


__all__ = ["ProductionReadinessSweepWorker"]
