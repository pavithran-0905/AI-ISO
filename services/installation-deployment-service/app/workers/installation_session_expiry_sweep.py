"""The installation session expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every installation session that has been ``RUNNING`` past its own
configured maximum age -- an installer that never reports back is not
still "in progress" forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import InstallationSessionStatus
from app.services.bundle import build_repositories
from app.services.installer import InstallationSessionService
from app.services.notifications import DeploymentNotifier

logger = get_logger("app.workers.installation_session_expiry_sweep")


class InstallationSessionExpirySweepWorker:
    """Fails stale installation sessions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: DeploymentNotifier,
        max_age_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running installation sessions,
        returning how many were failed."""
        now = datetime.now(UTC)
        before = now - timedelta(hours=self._max_age_hours)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = InstallationSessionService(
                repos.installation_sessions, notifier=self._notifier
            )

            for organization_id in await repos.installation_sessions.list_organization_ids():
                for installation_session in await repos.installation_sessions.list_running(
                    organization_id
                ):
                    if (
                        installation_session.started_at is not None
                        and installation_session.started_at < before
                    ):
                        await service.complete(
                            installation_session,
                            status=InstallationSessionStatus.FAILED,
                            now=now,
                            reason="Installation session timed out.",
                        )
                        failed += 1
            await session.commit()

        logger.info(
            "installation session expiry sweep completed",
            extra={"extra_fields": {"failed": failed}},
        )
        return failed


__all__ = ["InstallationSessionExpirySweepWorker"]
