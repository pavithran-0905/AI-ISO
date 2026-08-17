"""The developer session expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires every active portal session past its own ``expires_at``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.developers import DeveloperSessionService

logger = get_logger("app.workers.session_expiry_sweep")


class DeveloperSessionExpirySweepWorker:
    """Expires stale developer portal sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's active sessions, returning how
        many were checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = DeveloperSessionService(repos.sessions)
            organization_ids = await repos.sessions.list_organization_ids()

            for organization_id in organization_ids:
                for developer_session in await repos.sessions.list_active(organization_id):
                    if service.is_expired(developer_session, now=now):
                        await service.expire(developer_session)
                    checked += 1
            await session.commit()

        logger.info(
            "developer session expiry sweep completed", extra={"extra_fields": {"checked": checked}}
        )
        return checked


__all__ = ["DeveloperSessionExpirySweepWorker"]
