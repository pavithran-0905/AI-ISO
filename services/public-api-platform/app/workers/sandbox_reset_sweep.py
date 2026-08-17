"""The sandbox reset sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Resets every sandbox session that has outlived its own configured
maximum age -- docs/073's SANDBOX section names "Reset Sandbox" as a
first-class capability, not just something a developer triggers
manually.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.sandbox.engine import is_sandbox_session_stale
from app.services.bundle import build_repositories
from app.services.sandbox import SandboxService

logger = get_logger("app.workers.sandbox_reset_sweep")


class SandboxResetSweepWorker:
    """Resets stale developer sandbox sessions."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, max_age_hours: int
    ) -> None:
        self._session_factory = session_factory
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's active sandbox sessions,
        returning how many were reset."""
        now = datetime.now(UTC)
        reset_count = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            sandbox_service = SandboxService(repos.api_sandbox)

            for organization_id in await repos.api_sandbox.list_organization_ids():
                for sandbox_session in await repos.api_sandbox.list_active(organization_id):
                    if is_sandbox_session_stale(
                        last_reset_at=sandbox_session.last_reset_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await sandbox_service.reset(sandbox_session, now=now)
                        reset_count += 1
            await session.commit()

        logger.info("sandbox reset sweep completed", extra={"extra_fields": {"reset": reset_count}})
        return reset_count


__all__ = ["SandboxResetSweepWorker"]
