"""The API key expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires any active API key whose ``expires_at`` has passed -- a key
nobody rotated does not silently keep authenticating past what it was
actually issued for.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api_management.engine import is_key_expired
from app.models.enums import ApiKeyStatus
from app.services.api_keys import ApiKeyService
from app.services.bundle import build_repositories

logger = get_logger("app.workers.api_key_expiry_sweep")


class ApiKeyExpirySweepWorker:
    """Expires API keys past their expiry."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's API keys, returning how many
        were expired."""
        now = datetime.now(UTC)
        expired = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = ApiKeyService(repos.api_keys, repos.api_usage)

            for organization_id in await repos.api_keys.list_organization_ids():
                for key in await repos.api_keys.list_by_status(
                    organization_id, status=ApiKeyStatus.ACTIVE
                ):
                    if is_key_expired(key.expires_at, now=now):
                        await service.expire(key)
                        expired += 1
            await session.commit()

        logger.info("API key expiry sweep completed", extra={"extra_fields": {"expired": expired}})
        return expired


__all__ = ["ApiKeyExpirySweepWorker"]
