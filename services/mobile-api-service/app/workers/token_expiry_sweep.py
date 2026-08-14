"""The token expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires every device-bound mobile token past its own ``expires_at`` --
security hygiene independent of session expiry: a session can end long
before its device's own long-lived offline token would otherwise still
be valid.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import TokenStatus
from app.services.bundle import build_repositories

logger = get_logger("app.workers.token_expiry_sweep")


class TokenExpirySweepWorker:
    """Expires stale device-bound tokens."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's active tokens, returning how many
        were expired."""
        now = datetime.now(UTC)
        expired = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            organization_ids = await repos.tokens.list_organization_ids()

            for organization_id in organization_ids:
                for token in await repos.tokens.list_active(organization_id):
                    if now >= token.expires_at:
                        token.status = TokenStatus.EXPIRED
                        await repos.tokens.update(token)
                        expired += 1
            await session.commit()

        logger.info("token expiry sweep completed", extra={"extra_fields": {"expired": expired}})
        return expired


__all__ = ["TokenExpirySweepWorker"]
