"""The retention sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Only the coarse-tier deletion in ``app.retention.engine``'s plan is
executed here.** The engine's raw and downsampled deletion tiers are
gated on a downsample watermark that only a downsampling worker can
advance -- and this build does not include one. Authorizing raw deletion
without it would be exactly the defect
:func:`app.retention.engine.plan_retention` exists to prevent: destroying
signal data before anything coarser has been produced to replace it. The
coarse cutoff carries no such dependency (it deletes anything, at any
resolution, past the policy's outer retention bound), so it is the one
tier safe to run unconditionally, and it is what keeps storage bounded
even without a downsampler.

A deployment that adds downsampling should extend this worker to pass a
real ``raw_downsampled_watermark`` rather than routing raw deletion
through this file's logic from scratch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import SignalKind
from app.retention.engine import RetentionPlan
from app.services.bundle import Repositories, build_repositories
from app.services.retention import RetentionService

logger = get_logger("app.workers.retention_sweep")

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

_PURGERS: dict[SignalKind, str] = {
    SignalKind.METRIC: "metrics",
    SignalKind.LOG: "logs",
    SignalKind.TRACE: "trace_spans",
    SignalKind.EVENT: "events",
    SignalKind.PROFILE: "profiles",
}
"""Which repository on the bundle owns each signal kind's raw table.
``SignalKind.TOPOLOGY`` has no row-level table to purge -- topology is
derived and re-upserted by :class:`app.workers.topology_rebuild
.TopologyRebuildWorker` on its own schedule, so there is nothing here
for it to delete."""


class RetentionSweepWorker:
    """Applies the coarse-tier retention cutoff for every enabled policy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Purge every policy's coarse tier, returning rows deleted."""
        now = datetime.now(UTC)
        total_deleted = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = RetentionService(repos.retention_policies)

            for organization_id in await repos.retention_policies.list_organization_ids():
                for policy in await repos.retention_policies.list_enabled(organization_id):
                    plan = await service.plan_for_policy(
                        policy,
                        now=now,
                        epoch=_EPOCH,
                        raw_downsampled_watermark=None,
                        downsampled_coarsened_watermark=None,
                    )
                    deleted = await self._apply_coarse_tier(
                        repos, organization_id, policy.signal_kind, plan
                    )
                    total_deleted += deleted
                    await service.record_sweep(
                        organization_id, policy.id, applied_at=now, deleted_count=deleted
                    )
            await session.commit()

        logger.info("retention sweep completed", extra={"extra_fields": {"deleted": total_deleted}})
        return total_deleted

    @staticmethod
    async def _apply_coarse_tier(
        repos: Repositories, organization_id: UUID, signal_kind: SignalKind, plan: RetentionPlan
    ) -> int:
        attr = _PURGERS.get(signal_kind)
        if attr is None:
            return 0
        repo = getattr(repos, attr)
        deleted = 0
        for action in plan.delete_actions:
            if action.resolution != "coarse":
                continue
            deleted += await repo.purge_older_than(organization_id, older_than=action.older_than)
        return deleted


__all__ = ["RetentionSweepWorker"]
