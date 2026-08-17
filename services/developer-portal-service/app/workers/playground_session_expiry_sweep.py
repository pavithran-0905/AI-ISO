"""The playground session expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires every active code playground session that has been idle past
its own configured maximum age.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.playground.engine import is_playground_session_stale
from app.services.bundle import build_repositories
from app.services.explorer import PlaygroundService

logger = get_logger("app.workers.playground_session_expiry_sweep")


class PlaygroundSessionExpirySweepWorker:
    """Expires stale code playground sessions."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, max_age_hours: int
    ) -> None:
        self._session_factory = session_factory
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's active playground sessions,
        returning how many were expired."""
        now = datetime.now(UTC)
        expired = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = PlaygroundService(repos.playground_sessions)
            organization_ids = await repos.playground_sessions.list_organization_ids()

            for organization_id in organization_ids:
                for playground_session in await repos.playground_sessions.list_active(
                    organization_id
                ):
                    if is_playground_session_stale(
                        last_active_at=playground_session.last_active_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        await service.expire(playground_session)
                        expired += 1
            await session.commit()

        logger.info(
            "playground session expiry sweep completed",
            extra={"extra_fields": {"expired": expired}},
        )
        return expired


__all__ = ["PlaygroundSessionExpirySweepWorker"]
