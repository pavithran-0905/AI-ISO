"""The retention sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Applies every enabled retention policy's tiering and deletion plan,
with immutability and legal hold enforced by
``app.retention.engine.is_deletable`` -- never bypassed here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.retention import RetentionService

logger = get_logger("app.workers.retention_sweep")


class RetentionSweepWorker:
    """Applies every enabled retention policy for every organization."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Apply every enabled policy, returning archives deleted."""
        now = datetime.now(UTC)
        total_deleted = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = RetentionService(repos.retention, repos.archives)

            for organization_id in await repos.retention.list_organization_ids():
                for policy in await repos.retention.list_enabled(organization_id):
                    archives = await repos.archives.list_for_target_kind(
                        organization_id, policy.target_kind
                    )
                    plan = service.plan_for_policy(policy, list(archives), now=now)
                    archives_by_id = {str(a.id): a for a in archives}
                    deleted = await service.apply_plan(plan, archives_by_id)
                    await service.record_sweep(
                        organization_id, policy.id, applied_at=now, deleted_count=deleted
                    )
                    total_deleted += deleted
            await session.commit()

        logger.info("retention sweep completed", extra={"extra_fields": {"deleted": total_deleted}})
        return total_deleted


__all__ = ["RetentionSweepWorker"]
