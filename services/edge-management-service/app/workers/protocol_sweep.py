"""The protocol sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Reclassifies every protocol endpoint's connectivity status against the
current time -- a connection nothing has actually checked recently drifts
from ``CONNECTED`` to ``UNKNOWN`` on its own as staleness accrues, even
with no new check ever recorded.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.protocols.engine import classify_connectivity
from app.services.bundle import build_repositories

logger = get_logger("app.workers.protocol_sweep")


class ProtocolSweepWorker:
    """Reclassifies every protocol endpoint's connectivity status."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, stale_after_minutes: int
    ) -> None:
        self._session_factory = session_factory
        self._stale_after_minutes = stale_after_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Reclassify every protocol endpoint, returning how many were
        checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.protocols.list_organization_ids():
                for device in await repos.devices.list_recent(organization_id, limit=5000):
                    for protocol in await repos.protocols.list_for_device(device.id):
                        protocol.status = classify_connectivity(
                            protocol.last_checked_at,
                            had_error=protocol.error_message is not None,
                            now=now,
                            stale_after_minutes=self._stale_after_minutes,
                        )
                        await repos.protocols.update(protocol)
                        checked += 1
            await session.commit()

        logger.info("protocol sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["ProtocolSweepWorker"]
