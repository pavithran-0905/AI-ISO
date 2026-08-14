"""The session expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires every active session past its own ``expires_at``, and notifies
Session Expiring for any session inside its own warning window. There
is no "already notified" flag on ``mobile_sessions``, so a session that
stays in its warning window across multiple ticks is notified again
each time -- an accepted, documented limitation rather than a schema
change to add idempotency tracking this prompt's scope does not call
for.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.authentication.engine import is_session_expiring_soon
from app.services.bundle import build_repositories
from app.services.notifications import MobileNotifier
from app.services.sessions import SessionService

logger = get_logger("app.workers.session_expiry_sweep")


class SessionExpirySweepWorker:
    """Expires stale sessions and warns of imminent expiry."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: MobileNotifier,
        warning_minutes: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_minutes = warning_minutes

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
            session_service = SessionService(repos.sessions)
            organization_ids = await repos.sessions.list_organization_ids()

            for organization_id in organization_ids:
                active_sessions = await repos.sessions.list_active(organization_id)
                for mobile_session in active_sessions:
                    if session_service.is_expired(mobile_session, now=now):
                        await session_service.expire(mobile_session)
                    elif is_session_expiring_soon(
                        expires_at=mobile_session.expires_at,
                        now=now,
                        warning_minutes=self._warning_minutes,
                    ):
                        device = await repos.devices.get_by_id(mobile_session.device_id)
                        device_identifier = (
                            device.device_identifier if device is not None else "unknown"
                        )
                        await self._notifier.notify_session_expiring(
                            device_identifier=device_identifier,
                            expires_at=mobile_session.expires_at.isoformat(),
                        )
                    checked += 1
            await session.commit()

        logger.info("session expiry sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["SessionExpirySweepWorker"]
