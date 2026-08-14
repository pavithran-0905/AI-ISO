"""The session expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Disables any enabled CLI session whose ``expires_at`` has passed -- a
session nobody logged out of does not silently keep authenticating past
what it was actually issued for.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.authentication.engine import is_session_expired
from app.services.bundle import build_repositories

logger = get_logger("app.workers.session_expiry_sweep")


class SessionExpirySweepWorker:
    """Disables CLI sessions past their expiry."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's enabled CLI sessions, returning
        how many were expired."""
        now = datetime.now(UTC)
        expired = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.cli_sessions.list_organization_ids():
                for cli_session in await repos.cli_sessions.list_enabled(organization_id):
                    if is_session_expired(cli_session.expires_at, now=now):
                        cli_session.is_enabled = False
                        await repos.cli_sessions.update(cli_session)
                        expired += 1
            await session.commit()

        logger.info("session expiry sweep completed", extra={"extra_fields": {"expired": expired}})
        return expired


__all__ = ["SessionExpirySweepWorker"]
